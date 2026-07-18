# 🚀 ANKA Finance — Store Submission Guide

Everything you need to submit to the **Apple App Store** and **Google Play Store**.

---

## What I've Already Done For You

### ✅ Code & Configuration Fixed
| File | What Changed |
|------|-------------|
| `mobile/app.json` | App name → "ANKA Finance", production API URL, EAS project ID |
| `mobile/.env` | All production values (domain, email, URLs) |
| `mobile/.env.example` | Updated to match production |
| `mobile/eas.json` | Build profiles with env vars, submit config with placeholders |
| `mobile/tsconfig.json` | Fixed deprecated `moduleResolution` |
| `mobile/app-privacy-details.json` | Complete App Store privacy questionnaire answers |
| `.env` | Production-ready with `ankafinance.com` domain |
| `templates/privacy.html` | Support email → `support@ankafinance.com` |
| `templates/terms.html` | Support email → `support@ankafinance.com` |
| `mobile/src/screens/SettingsScreen.tsx` | Support email → `support@ankafinance.com` |
| `mobile/src/screens/AuthScreen.tsx` | App name → "ANKA Finance" |
| `README.md` | App name → "ANKA Finance" |
| `scripts/seed_demo_data.py` | **NEW** — seeds a demo account with 50+ transactions, 5 accounts, budgets, goals, investments |
| `STORE_LISTING_METADATA.md` | **NEW** — all descriptions, keywords, screenshots for copy-paste |
| `deployment/railway.toml` | Added healthcheck endpoint |
| `.github/workflows/deploy.yml` | **NEW** — GitHub Actions CI/CD pipeline |
| `mobile/assets/README.md` | Detailed artwork specs |

---

## Step 1: 🏪 Create Developer Accounts (Cost Required)

| Store | Cost | Sign Up Link |
|-------|------|-------------|
| **Apple Developer** | **$99/year** | https://developer.apple.com/programs/enroll/ |
| **Google Play** | **$25 one-time** | https://play.google.com/console/signup |

---

## Step 2: 🌐 Deploy Backend to Production

### Option A: Railway (Recommended)
1. Push code to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Set environment variables (copy from `.env`):
   ```
   SECRET_KEY=<generate a random 64-char string>
   JWT_SECRET=<generate a different random 64-char string>
   APP_URL=https://ankafinance.com
   APP_NAME=ANKA Finance
   SUPPORT_EMAIL=support@ankafinance.com
   PRIVACY_URL=https://ankafinance.com/privacy
   TERMS_URL=https://ankafinance.com/terms
   ```
4. Add a custom domain (e.g., `ankafinance.com`)

### Option B: Render
1. In `deployment/render.yaml` — it's pre-configured
2. Connect repo → Render auto-deploys

### Option C: Fly.io
```bash
fly launch
fly secrets set SECRET_KEY=... JWT_SECRET=...
fly deploy
```

### After Deploying — Seed Demo Data
```bash
curl -X POST https://ankafinance.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo User","email":"demo@ankafinance.com","password":"DemoTest123!"}'
```

Then run the seeder script locally or on the server:
```bash
cd scripts
python seed_demo_data.py
```

---

## Step 3: 💳 Set Up Stripe (Web Billing)
1. Go to https://dashboard.stripe.com/
2. Create two **Products** → **Recurring**:
   - **ANKA Finance Plus** — $4.99/month
   - **ANKA Finance Family** — $9.99/month
3. Copy the **Price IDs** (starts with `price_`)
4. Set in your production env:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PRICE_PLUS=price_abc123
   STRIPE_PRICE_FAMILY=price_xyz789
   ```
5. Create a webhook in Stripe Dashboard pointing to:
   `https://ankafinance.com/billing/webhook`
   - Listen for: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`

---

## Step 4: 🍎 Apple App Store Connect Setup

### Create App Record
1. Go to https://appstoreconnect.apple.com → My Apps → +
2. **Name**: ANKA Finance
3. **Bundle ID**: `com.advait.personalfinancetracker`
4. **SKU**: `com.advait.personalfinancetracker`

### Create Subscriptions
1. In App Store Connect → Features → In-App Purchases → +
2. Create **Auto-Renewable Subscription**:
   - **Reference Name**: ANKA Finance Plus
   - **Product ID**: `com.advait.personalfinancetracker.plus.monthly`
   - **Price**: $4.99/month
3. Create another:
   - **Reference Name**: ANKA Finance Family
   - **Product ID**: `com.advait.personalfinancetracker.family.monthly`
   - **Price**: $9.99/month

### Get Shared Secret
1. App Store Connect → Features → In-App Purchases → View Shared Secret
2. Copy it → set as `APPLE_SHARED_SECRET` in server env

### Fill In App Information
Use `STORE_LISTING_METADATA.md` for all descriptions, keywords, etc.

### Privacy Questionnaire
Use `mobile/app-privacy-details.json` to fill in the App Privacy section.

### Add Demo Account
In Review Notes, add:
```
Demo account:
Email: demo@ankafinance.com
Password: DemoTest123!
This account has pre-loaded sample data for reviewing all features.
```

### Submit for Review
1. Build with EAS: `npx eas build --platform ios --profile production`
2. Upload to TestFlight: `npx eas submit --platform ios`
3. Test internally in TestFlight
4. Submit to App Review

---

## Step 5: 🤖 Google Play Console Setup

### Create App
1. Go to https://play.google.com/console → Create app
2. **Name**: ANKA Finance
3. **Package name**: `com.advait.personalfinancetracker`

### Create Subscriptions
1. Play Console → Monetize → Products → Subscriptions → +
2. Create:
   - **Product ID**: `com.advait.personalfinancetracker.plus.monthly`
   - **Name**: ANKA Finance Plus
   - **Price**: $4.99/month
3. Create:
   - **Product ID**: `com.advait.personalfinancetracker.family.monthly`
   - **Name**: ANKA Finance Family
   - **Price**: $9.99/month

### Service Account
1. Google Cloud Console → APIs & Services → Credentials
2. Create Service Account → Download JSON key
3. Enable Android Publisher API
4. Upload the JSON key to your server and set `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON`

### Fill In Store Listing
Use `STORE_LISTING_METADATA.md` for all descriptions, screenshots, etc.

### ❗ IMPORTANT — Closed Testing Requirement
If this is a **new Play Console account**, you MUST:
1. Create a **Closed Test** track
2. Add **12+ tester emails** (friends, family, testers)
3. Share the opt-in link
4. Run for **14+ days**
5. After 14 days, apply for **Production Access**
6. Once approved → promote to production

### Submit to Production
```bash
npx eas build --platform android --profile production
npx eas submit --platform android
```

---

## Step 6: 🎨 Final Artwork Needed

These **cannot be generated programmatically** — you need a designer or tool:

| Asset | Size | Where to Upload |
|-------|------|----------------|
| App Icon (iOS) | 1024×1024 PNG | Xcode / App Store Connect |
| App Icon (Android) | 1024×1024 PNG adaptive | Google Play Console |
| Feature Graphic | 1024×500 PNG | Google Play Console |
| iOS Screenshots (6.5") | 1284×2778 (2-4 needed) | App Store Connect |
| Android Screenshots | 1080×2340 (2-8 needed) | Google Play Console |

**Tools to generate screenshots:**
- [Apple Screenshots](https://developer.apple.com/app-store/product-page/) — Use Xcode simulator
- [Google Play Screenshot Builder](https://play.google.com/console/about/)
- [AppMockUp](https://app-mockup.com/) — Third-party tool
- [Screenshot Magic](https://screenshotmagic.com/) — Quick mockups

---

## Step 7: ⚖️ Legal

The `privacy.html` and `terms.html` templates are working drafts. **Before launch**, have them reviewed by a lawyer to ensure compliance with:
- **GDPR** (European users)
- **CCPA** (California users)
- **App Store Review Guidelines** (required privacy policy URL)
- **Google Play Data Safety** requirements

---

## 📋 Final Checklist

- [ ] Apple Developer account paid ($99)
- [ ] Google Play Developer account paid ($25)
- [ ] Domain purchased (e.g., ankafinance.com)
- [ ] Backend deployed to production with HTTPS
- [ ] All env vars set on production server
- [ ] Stripe products created with price IDs
- [ ] Apple subscriptions created in App Store Connect
- [ ] Google Play subscriptions created
- [ ] Apple shared secret copied to server
- [ ] Google Play service account JSON on server
- [ ] Demo account seeded and working
- [ ] App icons replaced (1024×1024)
- [ ] Splash screen replaced
- [ ] Feature graphic created (Google Play)
- [ ] Screenshots taken and uploaded (2-4 minimum)
- [ ] Privacy policy URL live and working
- [ ] Terms of service URL live and working
- [ ] Privacy questionnaire filled in (App Store)
- [ ] Data safety form filled in (Google Play)
- [ ] Age rating completed
- [ ] Demo account credentials in review notes
- [ ] Account deletion confirmed working
- [ ] Support email monitored and responsive
- [ ] iOS build submitted to TestFlight
- [ ] Android build submitted to closed test (if new account)
- [ ] Production submission sent!

---

## ⚡ Quick Commands Reference

```bash
# Install mobile deps
cd mobile && npm install

# Login to Expo/EAS
npx eas login

# Build everything
npx eas build --platform all --profile production

# Submit to stores
npx eas submit --platform ios
npx eas submit --platform android

# Seed demo data
cd scripts && python seed_demo_data.py

# Run tests
python -m pytest tests/ -v