# InstaTool APK — decoded source (reference copy)

Decoded from `base (4).apk` (package `com.example.instatool`) with androguard 4.1.4
(`androguard decompile -l 'Lcom/example/instatool/.*'`). Re-create with the same command.

## What is here
- `java/` — 55 decompiled classes. Names are R8-obfuscated (`j8.java`, `pm.java`, …), so the
  file names do not match the original classes. Some methods failed to decompile
  ("Multiple exit nodes" errors) and show bytecode instead; treat as a reading aid, not a build.
- `web-assets/` — the bundled WebView extension scripts and pages (`assets/instatool/`,
  `assets/extensions/captcha/`) as text. `dist/` bundles are minified.

## Not copied (on purpose)
- `assets/credentials.json` — a Google service-account key. Not copied. Rotate it in Google Cloud
  and stop shipping it inside the APK.
- Captcha model binaries and images.

## Key spots
- `java/j8.java` — Yamin mail API: `https://email.yamin.bd/apis.php?action=app&version=` (version check).
  The `getMessages` / `readMessage` URLs exist only as strings in `classes.dex`; the decompiler
  did not reproduce the methods that use them, so they are not in `java/`.
- `java/pm.java` — loads `credentials.json` at runtime and signs a Google JWT from it.
- `web-assets/instatool/extension_api.js` — page-to-native bridge (`config.bridge`, JSON messages).
- Shared Yamin key: same value as `engine/eng_constants.py` (env `YAMIN_AUTH_KEY`). Not copied here.
