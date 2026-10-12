#!/system/bin/sh
# Unattended trial only: return to recovery after repeated failures or 20 minutes (PixelOS first-boot optimization).
g9650_counter=/data/g9650-debug/attempts
g9650_attempt=0
if [ -f "$g9650_counter" ]; then
    read -r g9650_attempt < "$g9650_counter"
fi
case "$g9650_attempt" in ''|*[!0-9]*) g9650_attempt=0 ;; esac
g9650_attempt=$((g9650_attempt + 1))
echo "$g9650_attempt" > "$g9650_counter"
/system/bin/chmod 0640 "$g9650_counter"
/system/bin/sync
if [ "$g9650_attempt" -gt 3 ]; then
    echo '<3>G9650Compat: repeated incomplete boots; returning to recovery' > /dev/kmsg
    /system/bin/setprop sys.powerctl reboot,recovery
    exit 1
fi
g9650_elapsed=0
while [ "$g9650_elapsed" -lt 1200 ]; do
    if [ "$(/system/bin/getprop sys.boot_completed)" = 1 ]; then
        /system/bin/rm -f "$g9650_counter"
        echo '<6>G9650Compat: boot completed; recovery fallback disarmed' > /dev/kmsg
        exit 0
    fi
    /system/bin/sleep 5
    g9650_elapsed=$((g9650_elapsed + 5))
done
echo '<3>G9650Compat: no boot completion after 1200 seconds; returning to recovery' > /dev/kmsg
/system/bin/setprop sys.powerctl reboot,recovery
