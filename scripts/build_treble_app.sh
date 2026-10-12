#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd "$1" && pwd)
: "${ANDROID_HOME:?Set ANDROID_HOME to an SDK with platform 33 and build-tools 33.0.2}"
: "${JAVA_HOME:?Set JAVA_HOME to JDK 17}"
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_OPTS="${GRADLE_OPTS:-} -Dorg.gradle.daemon=false -Dorg.gradle.workers.max=8"
cd "$source_dir/treble_app"
./gradlew assembleRelease
"$ANDROID_HOME/build-tools/33.0.2/apksigner" sign --key keys/platform.pk8 --cert keys/platform.x509.pem \
  --out TrebleApp.apk app/build/outputs/apk/release/app-release-unsigned.apk
"$ANDROID_HOME/build-tools/33.0.2/apksigner" verify TrebleApp.apk
cp TrebleApp.apk "$source_dir/vendor/hardware_overlay/TrebleApp/app.apk"
sha256sum "$source_dir/vendor/hardware_overlay/TrebleApp/app.apk"
