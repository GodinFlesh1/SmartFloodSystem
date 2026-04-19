"""
Train an XGBoost flood prediction model on flood_dataset.csv.

Key changes over naive training:
  - Uses PAST water-level lags only (no current-level-vs-threshold feature
    dominating the model)
  - Uses FUTURE rainfall forecast features that match what the predictor
    fetches at inference time (Open-Meteo forecast_days)
  - Gentler class-imbalance handling — sqrt(neg/pos) instead of raw ratio —
    to keep probabilities well-calibrated
  - Isotonic calibration via CalibratedClassifierCV on a held-out slice
  - Chooses the decision threshold that maximises F1 on validation data
    (saved to models/decision_threshold.json for the backend to use)

Usage:
  python train.py           # train and save model
  python train.py --eval    # train, save, and show evaluation plots

Outputs:
  models/flood_model.pkl          — calibrated classifier
  models/feature_columns.json     — ordered feature names used at inference
  models/decision_threshold.json  — optimal probability cutoff + thresholds
  models/training_report.txt      — metrics summary
"""

import json
import argparse
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    f1_score,
    precision_recall_curve,
    average_precision_score,
)
from xgboost import XGBClassifier

DATA_PATH     = Path(__file__).parent / "data" / "processed" / "flood_dataset.csv"
MODELS_DIR    = Path(__file__).parent / "models"
MODEL_PATH    = MODELS_DIR / "flood_model.pkl"
FEATURES_PATH = MODELS_DIR / "feature_columns.json"
THRESHOLD_PATH = MODELS_DIR / "decision_threshold.json"
REPORT_PATH   = MODELS_DIR / "training_report.txt"

# ── Features the model uses at inference time ────────────────────────────────
# All past-only (water level) + past-and-future rainfall forecast. Rainfall
# uses forecast data that the backend fetches via Open-Meteo forecast_days.
FEATURE_COLS = [
    # Water level — current + PAST only
    "water_level",
    "level_lag_1d",
    "level_lag_3d",
    "level_lag_7d",
    "level_change_1d",
    "level_change_3d",
    "level_roll_7d",
    "level_roll_max_7d",
    # Threshold proximity — PAST level / threshold (not current)
    "level_pct_lag_1d",
    "level_pct_lag_3d",
    "lag1_above_threshold",
    # Rainfall — past accumulation
    "rain_past_1d",
    "rain_past_3d",
    "rain_past_7d",
    "rain_past_14d",
    # Rainfall — future forecast (available at inference from weather API)
    "rain_next_1d",
    "rain_next_3d",
    # Other weather
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
    # Calendar
    "month",
    "day_of_year",
    # Location
    "latitude",
    "longitude",
]


def load_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DATA_PATH}\n"
            "Run: python collect_all.py  first."
        )
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    print(f"Loaded {len(df):,} rows from {df['station_id'].nunique()} stations")
    print(f"Flood events: {df['flood'].sum():,} ({df['flood'].mean()*100:.1f}%)")
    return df


def time_based_split(df: pd.DataFrame, train_frac: float = 0.70, val_frac: float = 0.15):
    """Split by date: train | validation (for calibration/threshold) | test."""
    df = df.sort_values("date")
    n = len(df)
    train_end = df["date"].quantile(train_frac)
    val_end   = df["date"].quantile(train_frac + val_frac)

    train = df[df["date"] <= train_end]
    val   = df[(df["date"] > train_end) & (df["date"] <= val_end)]
    test  = df[df["date"] > val_end]

    print(f"Train: {len(train):,} rows ({train['date'].min().date()} → {train['date'].max().date()})")
    print(f"Val  : {len(val):,} rows ({val['date'].min().date()} → {val['date'].max().date()})")
    print(f"Test : {len(test):,} rows ({test['date'].min().date()} → {test['date'].max().date()})")
    return train, val, test


def find_best_threshold(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Decision threshold that maximises F1 on validation predictions."""
    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    # Last value of prec/rec has no matching threshold
    f1 = np.where(
        (prec[:-1] + rec[:-1]) > 0,
        2 * prec[:-1] * rec[:-1] / (prec[:-1] + rec[:-1]),
        0.0,
    )
    if len(f1) == 0:
        return 0.5
    best_idx = int(np.argmax(f1))
    return float(thr[best_idx])


def train(show_eval: bool = False):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load & split ──────────────────────────────────────────────────────────
    df = load_dataset()
    df = df.dropna(subset=FEATURE_COLS + ["flood"])
    print(f"After dropping NaN features: {len(df):,} rows")

    train_df, val_df, test_df = time_based_split(df)

    X_train, y_train = train_df[FEATURE_COLS], train_df["flood"]
    X_val,   y_val   = val_df[FEATURE_COLS],   val_df["flood"]
    X_test,  y_test  = test_df[FEATURE_COLS],  test_df["flood"]

    # ── Handle class imbalance gently ─────────────────────────────────────────
    # Using raw neg/pos ratio (~9×) inflates probabilities and wrecks
    # calibration. sqrt keeps the model sensitive to minority class without
    # over-predicting floods. We additionally rely on probability calibration
    # and a tuned decision threshold.
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale = round(np.sqrt(neg / pos), 2) if pos > 0 else 1.0
    print(f"\nClass balance — non-flood: {neg:,}  flood: {pos:,}  scale_pos_weight (sqrt): {scale}")

    # ── Train XGBoost base model ──────────────────────────────────────────────
    print("\nTraining XGBoost base model...")
    base_model = XGBClassifier(
        n_estimators=500,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,          # discourages tiny noisy leaves
        reg_lambda=1.0,
        scale_pos_weight=scale,
        eval_metric="logloss",
        early_stopping_rounds=30,
        random_state=42,
        n_jobs=-1,
    )
    base_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    print(f"  best_iteration = {base_model.best_iteration}")

    # ── Calibrate probabilities on validation slice ───────────────────────────
    # Isotonic calibration fits a monotonic mapping from raw scores to
    # empirical frequencies — this fixes the probability inflation caused by
    # scale_pos_weight, so predict_proba means what it says.
    print("\nCalibrating probabilities (isotonic)...")
    calibrator = CalibratedClassifierCV(
        estimator=base_model,
        method="isotonic",
        cv="prefit",
    )
    calibrator.fit(X_val, y_val)

    # ── Pick decision threshold on validation (maximise F1) ───────────────────
    val_prob = calibrator.predict_proba(X_val)[:, 1]
    best_thr = find_best_threshold(y_val.to_numpy(), val_prob)
    print(f"  optimal decision threshold (F1): {best_thr:.3f}")

    # ── Evaluate on test set ──────────────────────────────────────────────────
    y_prob = calibrator.predict_proba(X_test)[:, 1]
    y_pred = (y_prob >= best_thr).astype(int)

    roc_auc = roc_auc_score(y_test, y_prob)
    avg_prec = average_precision_score(y_test, y_prob)
    f1      = f1_score(y_test, y_pred)
    report  = classification_report(y_test, y_pred, target_names=["No Flood", "Flood"])
    cm      = confusion_matrix(y_test, y_pred)

    print("\n" + "=" * 50)
    print("EVALUATION RESULTS (calibrated + tuned threshold)")
    print("=" * 50)
    print(report)
    print(f"ROC-AUC         : {roc_auc:.4f}")
    print(f"Avg Precision   : {avg_prec:.4f}")
    print(f"F1 @ thr={best_thr:.2f} : {f1:.4f}")
    print(f"\nConfusion Matrix:")
    print(f"  True Negatives  (correct no-flood): {cm[0][0]:,}")
    print(f"  False Positives (false alarm):       {cm[0][1]:,}")
    print(f"  False Negatives (missed flood):      {cm[1][0]:,}")
    print(f"  True Positives  (correct flood):     {cm[1][1]:,}")

    # ── Feature importance from the base (uncalibrated) model ─────────────────
    importance = pd.Series(base_model.feature_importances_, index=FEATURE_COLS)
    top10 = importance.nlargest(10)
    print(f"\nTop 10 most important features:")
    for feat, score in top10.items():
        print(f"  {feat:<35} {score:.4f}")

    # ── Save artefacts ────────────────────────────────────────────────────────
    thresholds = {
        "decision_threshold": best_thr,
        # Absolute calibrated-probability cuts shown in the UI. The decision
        # threshold above is a separate, F1-optimal internal cutoff.
        "risk_bands": {
            "severe":   0.60,
            "high":     0.40,
            "moderate": 0.20,
            "minimal":  0.08,
        },
    }
    THRESHOLD_PATH.write_text(json.dumps(thresholds, indent=2))

    report_text = (
        f"EcoFlood Model Training Report\n"
        f"{'='*50}\n"
        f"Dataset: {len(df):,} rows | {df['station_id'].nunique()} stations\n"
        f"Train/Val/Test: time-based {int(0.70*100)}/{int(0.15*100)}/{int(0.15*100)}\n\n"
        f"{report}\n"
        f"ROC-AUC       : {roc_auc:.4f}\n"
        f"Avg Precision : {avg_prec:.4f}\n"
        f"F1 (tuned)    : {f1:.4f}\n"
        f"Decision thr  : {best_thr:.4f}\n\n"
        f"Confusion Matrix:\n{cm}\n\n"
        f"Top 10 Features:\n{top10.to_string()}\n"
    )
    REPORT_PATH.write_text(report_text)

    joblib.dump(calibrator, MODEL_PATH)
    FEATURES_PATH.write_text(json.dumps(FEATURE_COLS, indent=2))

    print(f"\nModel saved     → {MODEL_PATH}")
    print(f"Features saved  → {FEATURES_PATH}")
    print(f"Threshold saved → {THRESHOLD_PATH}")
    print(f"Report saved    → {REPORT_PATH}")

    if show_eval:
        import matplotlib.pyplot as plt
        import seaborn as sns
        from sklearn.metrics import roc_curve

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
                    xticklabels=["No Flood", "Flood"],
                    yticklabels=["No Flood", "Flood"])
        axes[0].set_title(f"Confusion Matrix (thr={best_thr:.2f})")
        axes[0].set_ylabel("Actual")
        axes[0].set_xlabel("Predicted")

        fpr, tpr, _ = roc_curve(y_test, y_prob)
        axes[1].plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
        axes[1].plot([0, 1], [0, 1], "k--")
        axes[1].set_xlabel("False Positive Rate")
        axes[1].set_ylabel("True Positive Rate")
        axes[1].set_title("ROC Curve")
        axes[1].legend()

        top10.sort_values().plot(kind="barh", ax=axes[2])
        axes[2].set_title("Top 10 Feature Importances")
        axes[2].set_xlabel("Importance Score")

        plt.tight_layout()
        plot_path = MODELS_DIR / "evaluation.png"
        plt.savefig(plot_path, dpi=150)
        print(f"Evaluation plot → {plot_path}")
        plt.show()

    return calibrator


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true",
                        help="Show evaluation plots after training")
    args = parser.parse_args()
    train(show_eval=args.eval)
