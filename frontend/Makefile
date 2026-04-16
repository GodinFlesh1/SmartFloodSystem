ENV_DEV  = --dart-define-from-file=.env.json
ENV_PROD = --dart-define-from-file=.env.prod.json

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	flutter run $(ENV_DEV)

run-web:
	flutter run -d chrome $(ENV_DEV)

run-android:
	flutter run -d android $(ENV_DEV)

run-prod:
	flutter run $(ENV_PROD)

# ── Build ─────────────────────────────────────────────────────────────────────
build-apk:
	flutter build apk $(ENV_DEV)

build-apk-prod:
	flutter build apk --release $(ENV_PROD)

build-appbundle:
	flutter build appbundle --release $(ENV_PROD)

build-ios:
	flutter build ios --release $(ENV_PROD)

build-web:
	flutter build web $(ENV_DEV)

# ── Utils ─────────────────────────────────────────────────────────────────────
clean:
	flutter clean && flutter pub get

get:
	flutter pub get

.PHONY: run run-web run-android run-prod build-apk build-apk-prod build-appbundle build-ios build-web clean get
