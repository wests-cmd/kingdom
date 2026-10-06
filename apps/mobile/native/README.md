# Kingdom mobile companion

Native Android and iOS shells open the existing Kingdom HTTPS connection flow in the system’s secure browser. They do not run the backend, a local model or a standalone offline Kingdom runtime on the phone. Keep the Kingdom host online; private Tailscale addresses require the phone on the same tailnet.

Enter the server origin, then pair using the owner-created code on `/#/connect`. Only the server origin is remembered in this shell. Pairing codes and tokens remain in the browser session. Cleartext HTTP, embedded passwords, paths, query strings and fragments are rejected.

## Build and validation

`npm ci`, `npm test`, `npm run build`, and `npx cap sync` prepare the native projects. Android requires Java 21 and Android SDK 36. iOS requires the supported Xcode version on a Mac runner. `.github/workflows/mobile.yml` verifies a publisher-signed Android APK with the pinned certificate, starts it in an Android emulator and saves screenshots; the iPhone Simulator build is not an installable iPhone release.

Android signing uses `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` as GitHub secrets and `ANDROID_EXPECTED_CERT_SHA256` as a repository variable. Never commit private keys or passwords.

Signed iPhone distribution remains disabled until an Apple Developer Program account issues a certificate and profile for `com.westscmd.kingdom`. Required secrets: `IOS_CERTIFICATE_BASE64` (distribution P12), `IOS_CERTIFICATE_PASSWORD`, `IOS_PROVISIONING_PROFILE_BASE64`, `IOS_TEAM_ID`, `IOS_PROFILE_NAME`. Only then enable `KINGDOM_ENABLE_SIGNED_IOS_RELEASE=true`. App Store Connect/TestFlight export requires distribution through Apple; it is not a universally installable IPA from GitHub.

The version follows the associated Kingdom release; native mobile build number 1010201 identifies this initial companion. Android APK publication requires both build/signature checks and emulator validation to succeed. iOS simulator success does not enable iPhone distribution automatically.
