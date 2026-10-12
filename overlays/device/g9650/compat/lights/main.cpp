// G9650-only AIDL backlight adapter for Android releases without HIDL lights.
// Uses the existing panel driver, never writes calibration or firmware storage.
#include <aidl/android/hardware/light/BnLights.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android/log.h>
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <mutex>
#include <unistd.h>

using namespace aidl::android::hardware::light;
static constexpr const char* kPanel = "/sys/class/backlight/panel0-backlight/brightness";

class PanelLights : public BnLights {
  std::mutex lock_;
 public:
  ndk::ScopedAStatus getLights(std::vector<HwLight>* lights) override {
    HwLight backlight;
    backlight.id = 0;
    backlight.ordinal = 1;
    backlight.type = LightType::BACKLIGHT;
    *lights = {backlight};
    return ndk::ScopedAStatus::ok();
  }
  ndk::ScopedAStatus setLightState(int32_t id, const HwLightState& state) override {
    const uid_t caller = AIBinder_getCallingUid();
    if (caller != 0 && caller != 1000 && caller != 1003) {
      return ndk::ScopedAStatus::fromExceptionCode(EX_SECURITY);
    }
    if (id != 0) return ndk::ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
    std::lock_guard<std::mutex> guard(lock_);
    int value;
    if (state.flashMode == FlashMode::HARDWARE) {
      // TrebleDroid's S9 patch sends brightness * 100 in color, not ARGB.
      value = state.color;
    } else {
      const unsigned color = static_cast<unsigned>(state.color);
      const int intensity = ((color >> 16 & 255) * 77 + (color >> 8 & 255) * 150 + (color & 255) * 29) >> 8;
      value = intensity * 25500 / 255;
    }
    value = std::clamp(value, 0, 50000);
    const int fd = open(kPanel, O_WRONLY | O_CLOEXEC);
    if (fd < 0) return ndk::ScopedAStatus::fromServiceSpecificError(errno);
    char text[32];
    const int size = snprintf(text, sizeof(text), "%d\n", value);
    const ssize_t written = write(fd, text, size);
    const int error = errno;
    close(fd);
    if (written != size) return ndk::ScopedAStatus::fromServiceSpecificError(error ? error : EIO);
    return ndk::ScopedAStatus::ok();
  }
};

int main() {
  // Refuse to register a hardware adapter if this panel is absent.
  if (access(kPanel, W_OK)) {
    __android_log_print(ANDROID_LOG_ERROR, "G9650Lights", "Panel not writable: %s", strerror(errno));
    return 1;
  }
  ABinderProcess_setThreadPoolMaxThreadCount(1);
  auto lights = ndk::SharedRefBase::make<PanelLights>();
  const std::string name = std::string(ILights::descriptor) + "/default";
  const binder_status_t status = AServiceManager_addService(lights->asBinder().get(), name.c_str());
  if (status != STATUS_OK) {
    __android_log_print(ANDROID_LOG_ERROR, "G9650Lights", "Registration failed: %d", status);
    return 2;
  }
  __android_log_print(ANDROID_LOG_INFO, "G9650Lights", "AIDL backlight registered for existing G9650 panel");
  ABinderProcess_joinThreadPool();
  return 3;
}
