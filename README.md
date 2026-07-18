# ANKA Finance

A worldwide personal finance platform with a Flask web app, REST API, Stripe global billing, and an Expo mobile app for iOS and Android.

## Features

- User registration, login, and private finance workspaces
- Dashboard, accounts, transactions, budgets, goals, investments, reports
- **10 currencies** (USD, EUR, GBP, INR, CAD, AUD, JPY, SGD, AED, CHF)
- **Stripe** subscription checkout (135+ countries)
- **Apple / Google in-app purchase** verification for mobile
- **REST API** at `/api/v1` for the mobile app
- Plan enforcement (Plus required for reports and investments)

## Quick start (web)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`

## Stripe setup (worldwide web billing)

1. Create a [Stripe account](https://dashboard.stripe.com/register)
2. Create two recurring **Products** in Stripe Dashboard:
   - **Plus** — $4.99/month
   - **Family** — $9.99/month
3. Copy each Price ID into `.env`:
   ```
   STRIPE_PRICE_PLUS=price_...
   STRIPE_PRICE_FAMILY=price_...
   ```
4. Add your API keys and webhook secret
5. Create a webhook endpoint: `https://api.financetracker.app/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
6. Set `APP_URL=https://financetracker.app`

## Deploy backend (production)

Deploy to Railway, Render, Fly.io, or any host that supports Python:

```bash
gunicorn -w 2 -b 0.0.0.0:$PORT app:app
```

Set environment variables from `.env.example`. Use HTTPS and a strong `SECRET_KEY`.

## Mobile app (App Store + Google Play)

```bash
cd mobile
npm install
```

1. Update `app.json` → `extra.apiUrl` to your production API
2. Add app icons to `mobile/assets/` (see `mobile/assets/README.md`)
3. Create subscription products in App Store Connect and Google Play Console:
   - `com.financetracker.plus.monthly`
   - `com.financetracker.family.monthly`
4. Install [EAS CLI](https://docs.expo.dev/build/setup/) and run:

```bash
npx eas build --platform all
npx eas submit --platform ios
npx eas submit --platform android
```

### Developer accounts required

| Store | Cost | URL |
|-------|------|-----|
| Apple Developer | $99/year | developer.apple.com |
| Google Play | $25 one-time | play.google.com/console |

## API reference

Base URL: `/api/v1`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | No | Health check |
| GET | `/meta` | No | Plans, currencies, categories |
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | Get JWT token |
| GET | `/me` | Bearer | Current user |
| GET | `/dashboard` | Bearer | Dashboard summary |
| GET/POST | `/transactions` | Bearer | List / create |
| GET/POST | `/accounts` | Bearer | List / create |
| GET | `/budgets`, `/goals`, `/reports` | Bearer | Feature data |
| POST | `/billing/checkout` | Bearer | Stripe checkout URL |
| POST | `/billing/mobile/verify` | Bearer | Apple/Google receipt |

## Plans

| Plan | Price | Features |
|------|-------|----------|
| Free | $0 | Accounts, transactions, budgets, goals, CSV |
| Plus | $4.99/mo | + Reports, investments, budget alerts |
| Family | $9.99/mo | + Shared budgets, priority support |

## Legal before launch

Replace draft pages at `/privacy` and `/terms` with lawyer-reviewed policies. Add support email, refund policy, and data retention rules.

## Project structure

```
app.py              Web app entry point
finance/            Config, DB, billing, auth, currency
api/                REST API for mobile
templates/          Web UI
static/             CSS and PWA manifest
mobile/             Expo React Native app
```
