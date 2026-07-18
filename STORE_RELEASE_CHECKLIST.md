# Store release checklist

This project now contains the main code hooks needed for store review, but final submission still needs real external account setup.

## Required before building release binaries

- Replace all `your-domain.com`, `yourcompany`, and example support email values in `.env`, `mobile/.env`, and store listings.
- Deploy the Flask backend to HTTPS and set `APP_URL`, `PRIVACY_URL`, `TERMS_URL`, `SUPPORT_EMAIL`, `SECRET_KEY`, and `JWT_SECRET`.
- Configure a production database with backups.
- Configure Stripe web billing only for the web app.
- Configure Apple and Google subscriptions for:
  - `com.financetracker.plus.monthly`
  - `com.financetracker.family.monthly`
- Set `APPLE_SHARED_SECRET`.
- Create a Google Play service account JSON with Android Publisher API access and set `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`.
- Replace the generated icon and splash assets with final branded artwork before public launch.

## App Store Connect

- Create the app record using the final iOS bundle identifier.
- Add subscription products and pricing.
- Add privacy policy URL, support URL, screenshots, description, keywords, category, age rating, and app privacy answers.
- Add a demo reviewer account with sample data.
- Submit through TestFlight first, then App Review.

## Google Play Console

- Create the app record using the final Android package name.
- Add subscription products and pricing.
- Complete Data safety, content rating, target audience, app access, ads declaration, and financial features disclosures.
- Upload screenshots, feature graphic, short description, full description, privacy policy URL, and support email.
- If this is a new personal developer account, run the required closed test before applying for production access.

## Reviewer notes

Use notes like:

> Personal Finance Tracker lets users manually track accounts, transactions, budgets, goals, investments, and reports. It is not financial advice and does not connect to banks. Login is required because each user has a private finance workspace. Demo account: [email/password]. Subscriptions unlock advanced reports and investments. Account deletion is available in Settings.
