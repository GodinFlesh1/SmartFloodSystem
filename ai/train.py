"""
Train an XGBoost flood prediction model on flood_dataset.csv.

Usage:
  python train.py           # train and save model
  python train.py --eval    # train, save, and show detailed evaluation plots

Outputs:
  models/flood_model.pkl         — trained XGBoost classifier
  models/feature_columns.json    — ordered list of feature names (used by predictor)
  models/training_report.txt     — accuracy metrics summary
"""

import json
import argparse
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    f1_score,
)
from xgboost import XGBClassifier

DATA_PATH    = Path(__file__).parent / "data" / "processed" / "flood_dataset.csv"
MODELS_DIR   = Path(__file__).parent / "models"
MODEL_PATH   = MODELS_DIR / "flood_model.pkl"
FEATURES_PATH = MODELS_DIR / "feature_columns.json"
REPORT_PATH  = MODELS_DIR / "training_report.txt"

# Features the model will use at prediction time
FEATURE_COLS = [
    # Water level
    "water_level",
    "water_level_max",
    "water_level_min",
    # Level trends
    "level_lag_1d",
    "level_lag_3d",
    "level_lag_7d",
    "level_change_1d",
    "level_change_3d",
    "level_roll_7d",
    # Threshold proximity — past values only (no leakage)
    "level_above_typical_high",
    "level_pct_lag_1d",   # yesterday's level / threshold
    "level_pct_lag_3d",   # 3 days ago level / threshold
    # Rainfall
    "precipitation_sum",
    "rain_sum",
    "rain_3d",
    "rain_7d",
    "rain_14d",
    "rain_lag_1d",
    # Weather
    "temperature_2m_max",
    "temperature_2m_min",
    "wind_speed_10m_max",
    # Calendar — flood_season removed to prevent model relying on seasonality
    # instead of actual water/rain signals
    "month",
    "day_of_year",
    # Location (station characteristics)
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
    print(f"Loaded {len(df):,} rows from {len(df['station_id'].unique())} stations")
    print(f"Flood events: {df['flood'].sum():,} ({df['flood'].mean()*100:.1f}%)")
    return df


def time_based_split(df: pd.DataFrame):
    """
    Use the last 20% of dates as test set.
    This is more realistic than random split for time-series data —
    the model must predict future floods from past data.
    """
    df = df.sort_values("date")
    cutoff = df["date"].quantile(0.80)
    train = df[df["date"] <= cutoff]
    test  = df[df["date"] >  cutoff]
    print(f"Train: {len(train):,} rows ({train['date'].min().date()} → {train['date'].max().date()})")
    print(f"Test : {len(test):,} rows  ({test['date'].min().date()} → {test['date'].max().date()})")
    return train, test


def train(show_eval: bool = False):
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load & split ──────────────────────────────────────────────────────────
    df = load_dataset()

    # Only keep rows where all features are available
    df = df.dropna(subset=FEATURE_COLS + ["flood"])
    print(f"After dropping NaN features: {len(df):,} rows")

    train_df, test_df = time_based_split(df)

    X_train = train_df[FEATURE_COLS]
    y_train = train_df["flood"]
    X_test  = test_df[FEATURE_COLS]
    y_test  = test_df["flood"]

    # ── Handle class imbalance ────────────────────────────────────────────────
    # scale_pos_weight = ratio of negatives to positives
    neg = (y_train == 0).sum()
    pos = (y_train == 1).sum()
    scale = round(neg / pos, 2) if pos > 0 else 1
    print(f"\nClass balance — non-flood: {neg:,}  flood: {pos:,}  scale_pos_weight: {scale}")

    # ── Train XGBoost ─────────────────────────────────────────────────────────
    print("\nTraining XGBoost model...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale,   # compensate for class imbalance
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    y_pred      = model.predict(X_test)
    y_prob      = model.predict_proba(X_test)[:, 1]
    roc_auc     = roc_auc_score(y_test, y_prob)
    f1          = f1_score(y_test, y_pred)
    report      = classification_report(y_test, y_pred, target_names=["No Flood", "Flood"])
    cm          = confusion_matrix(y_test, y_pred)

    print("\n" + "=" * 50)
    print("EVALUATION RESULTS")
    print("=" * 50)
    print(report)
    print(f"ROC-AUC Score : {roc_auc:.4f}")
    print(f"F1 Score      : {f1:.4f}")
    print(f"\nConfusion Matrix:")
    print(f"  True Negatives  (correct no-flood): {cm[0][0]:,}")
    print(f"  False Positives (false alarm):       {cm[0][1]:,}")
    print(f"  False Negatives (missed flood):      {cm[1][0]:,}")
    print(f"  True Positives  (correct flood):     {cm[1][1]:,}")

    # Top features
    importance = pd.Series(model.feature_importances_, index=FEATURE_COLS)
    top10 = importance.nlargest(10)
    print(f"\nTop 10 most important features:")
    for feat, score in top10.items():
        print(f"  {feat:<35} {score:.4f}")

    # ── Save report ───────────────────────────────────────────────────────────
    report_text = (
        f"EcoFlood Model Training Report\n"
        f"{'='*50}\n"
        f"Dataset: {len(df):,} rows | {df['station_id'].nunique()} stations\n"
        f"Train/Test split: 80/20 time-based\n\n"
        f"{report}\n"
        f"ROC-AUC: {roc_auc:.4f}\n"
        f"F1:      {f1:.4f}\n\n"
        f"Confusion Matrix:\n{cm}\n\n"
        f"Top 10 Features:\n{top10.to_string()}\n"
    )
    REPORT_PATH.write_text(report_text)

    # ── Save model + feature list ─────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    FEATURES_PATH.write_text(json.dumps(FEATURE_COLS, indent=2))

    print(f"\nModel saved     → {MODEL_PATH}")
    print(f"Features saved  → {FEATURES_PATH}")
    print(f"Report saved    → {REPORT_PATH}")

    # ── Optional plots ────────────────────────────────────────────────────────
    if show_eval:
        import matplotlib.pyplot as plt
        import seaborn as sns
        from sklearn.metrics import roc_curve

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))

        # Confusion matrix
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=axes[0],
                    xticklabels=["No Flood", "Flood"],
                    yticklabels=["No Flood", "Flood"])
        axes[0].set_title("Confusion Matrix")
        axes[0].set_ylabel("Actual")
        axes[0].set_xlabel("Predicted")

        # ROC curve
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        axes[1].plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
        axes[1].plot([0, 1], [0, 1], "k--")
        axes[1].set_xlabel("False Positive Rate")
        axes[1].set_ylabel("True Positive Rate")
        axes[1].set_title("ROC Curve")
        axes[1].legend()

        # Feature importance
        top10.sort_values().plot(kind="barh", ax=axes[2])
        axes[2].set_title("Top 10 Feature Importances")
        axes[2].set_xlabel("Importance Score")

        plt.tight_layout()
        plot_path = MODELS_DIR / "evaluation.png"
        plt.savefig(plot_path, dpi=150)
        print(f"Evaluation plot → {plot_path}")
        plt.show()

    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", action="store_true",
                        help="Show evaluation plots after training")
    args = parser.parse_args()
    train(show_eval=args.eval)
