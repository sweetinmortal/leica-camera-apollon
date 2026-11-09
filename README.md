# Leica Camera compatibility patches for apollon

Community patches for `HolyBear_5.0.230706.0` on the Xiaomi Mi 10T Pro. The test device reported `M2007J3SG` and `apollo`, with LineageOS based on Android 17 (SDK 37), ARM64 and 4 KiB pages. LineageOS lists this variant as `apollon`. [Device page](https://wiki.lineageos.org/devices/apollon/variant2/)

The repository contains the build scripts, the bytecode edits and SHA-256 fingerprints of the local inputs. Xiaomi's APK and the device libraries come from the sources below.

## Changes and verification

- Use Android's standard stream configuration map when the donor's private constructor fails. This lets the camera module configure the preview on the tested framework.
- Use a regular Camera2 session for the photo `0x8001` branch and the front video `0x8009` branch. The latter triggered a buffer-import failure when recording. [Android session configuration](https://developer.android.com/reference/android/hardware/camera2/params/SessionConfiguration)
- Skip the two writes to MIUI's global headset setting that caused a permissions error when entering or leaving Video mode. Android handles audio routing.
- Log the camera module initialization exception while retaining its original error handling.

Device checks covered the live preview, rear JPEG capture at 6016 × 4512, and normal 1080p recording with the rear and front cameras. Night, portrait, slow motion, auxiliary lenses and other builds remain unverified.

The device tests ran with the existing global settings `hidden_api_policy=0` and `hidden_api_blacklist_exemptions=L`. The donor hit private API restrictions during earlier tests with the default policy. The collector uses read-only ADB commands and the repacker runs on the host. [Android non-SDK interfaces](https://developer.android.com/guide/app-compatibility/restrictions-non-sdk-interfaces)

## Rebuild locally

Use Python 3.9 or newer, Git with Git LFS, Android platform-tools, Android SDK build-tools with `zipalign -P` and `apksigner`, and a local signing key. Run the commands from this repository. Put `adb`, `zipalign` and `apksigner` on your PATH or use their full paths.

Get the APK and Xiaomi JNI library at the pinned donor commit. The donor uses Git LFS for the APK. [Donor commit](https://github.com/xaveroprjkt/vendor_MiuiLeicaCam/commit/94bcc2ae457e80c9d57787e1fa0c32de54ed63e8)

```text
git clone --branch dev --no-checkout https://github.com/xaveroprjkt/vendor_MiuiLeicaCam.git
git -C vendor_MiuiLeicaCam lfs install --local --skip-smudge
git -C vendor_MiuiLeicaCam checkout --detach 94bcc2ae457e80c9d57787e1fa0c32de54ed63e8
git -C vendor_MiuiLeicaCam lfs pull --include=system/priv-app/MiuiCamera/MiuiCamera.apk
```

Collect the matching libraries from your device or supply them from a local firmware extraction. Replace `DEVICE_SERIAL` with your device's identifier from `adb devices`. The collector checks the device family and SDK, then checks each library against `inputs.json`. A hash mismatch means you need the exact tested input bytes.

```text
python collect_libs.py --serial DEVICE_SERIAL --output device-libs
python build.py --donor-dir vendor_MiuiLeicaCam --libs-dir device-libs --output LeicaCamera-apollon-unsigned.apk
zipalign -P 4 4 LeicaCamera-apollon-unsigned.apk LeicaCamera-apollon-aligned.apk
apksigner sign --ks YOUR_KEYSTORE --out LeicaCamera-apollon-signed.apk LeicaCamera-apollon-aligned.apk
apksigner verify --print-certs LeicaCamera-apollon-signed.apk
zipalign -c -P 4 4 LeicaCamera-apollon-signed.apk
```

On a matching test device, install the signed APK as a user app. An existing `com.android.camera` package requires a matching signing certificate for an in-place update. Keep the same signing key for future rebuilds. Aperture uses a separate package and can stay available.

```text
adb -s DEVICE_SERIAL install --no-incremental -r LeicaCamera-apollon-signed.apk
```

The repacker checks the donor APK, the three modified DEX files and the native inputs before writing output. During validation, all non-signature entries in the rebuilt APK matched the handset-tested APK by SHA-256 and compression method. Local signatures and ZIP layout can differ.

## Credits and license

The donor inputs came from [xaveroprjkt/vendor_MiuiLeicaCam](https://github.com/xaveroprjkt/vendor_MiuiLeicaCam). The [MIT license](LICENSE) covers the scripts and documentation in this repository. Third-party inputs retain their respective rights.
