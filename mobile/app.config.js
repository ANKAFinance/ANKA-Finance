const app = require("./app.json");

const iosBundleIdentifier = process.env.IOS_BUNDLE_IDENTIFIER || app.expo.ios.bundleIdentifier;
const androidPackage = process.env.ANDROID_PACKAGE || app.expo.android.package;
const apiUrl = process.env.EXPO_PUBLIC_API_URL || app.expo.extra.apiUrl;
const easProjectId = process.env.EAS_PROJECT_ID || app.expo.extra.eas.projectId;

module.exports = {
  expo: {
    ...app.expo,
    name: process.env.APP_DISPLAY_NAME || app.expo.name,
    slug: process.env.APP_SLUG || app.expo.slug,
    ios: {
      ...app.expo.ios,
      bundleIdentifier: iosBundleIdentifier,
    },
    android: {
      ...app.expo.android,
      package: androidPackage,
    },
    extra: {
      ...app.expo.extra,
      apiUrl,
      supportEmail: process.env.SUPPORT_EMAIL || "support@financetracker.app",
      privacyUrl: process.env.PRIVACY_URL || "",
      termsUrl: process.env.TERMS_URL || "",
      eas: {
        ...app.expo.extra.eas,
        projectId: easProjectId,
      },
    },
  },
};
