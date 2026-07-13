# Flutter mobile testing

Witness drives Flutter apps through Appium so the QA loop stays user-facing: tap visible controls, enter text, scroll, observe screenshots, and judge what actually changed.

## Supported flow

- Android and iOS targets through Appium
- Real screenshots plus native accessibility/source snapshots
- Flutter project detection from `pubspec.yaml`, `android/`, `ios/`, and `lib/main.dart`
- Best-effort Android package/activity inference and iOS bundle-id discovery

## Minimal configuration

```yaml
project:
  type: mobile
  appium_server_url: http://127.0.0.1:4723
  mobile_platform_name: android   # or ios
  mobile_device_name: emulator-5554
  mobile_app: build/app/outputs/flutter-apk/app-debug.apk
  # Alternative for already-installed apps:
  # mobile_app_package: com.example.app
  # mobile_app_activity: .MainActivity
  # mobile_bundle_id: com.example.app
```

## Example

```bash
witness run --project . \
  --adapter mobile \
  --persona visual-bug-hunter \
  --journey "Sign in and reach the home screen"
```

## Notes

- Start Appium before launching Witness.
- Flutter semantics/accessibility labels substantially improve locator quality.
- For the highest-signal runs, use a real device or a production-like emulator/simulator image.
