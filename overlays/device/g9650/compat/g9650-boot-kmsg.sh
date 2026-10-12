#!/system/bin/sh
# Preserve crypto checks. Record both kernel and Android userspace failures.
umask 027
/system/bin/chown 0:2000 /data/g9650-debug/kernel.log /data/g9650-debug/environment.txt 2>/dev/null
/system/bin/dmesg -w > /data/g9650-debug/kernel.log 2>&1 &
g9650_log_pid=$!
/system/bin/logcat -b all -v threadtime -f /data/g9650-debug/logcat.txt -r 8192 -n 2 &
/system/bin/chown 0:2000 /data/g9650-debug/kernel.log /data/g9650-debug/logcat.txt 2>/dev/null
/system/bin/chmod 0640 /data/g9650-debug/kernel.log /data/g9650-debug/logcat.txt 2>/dev/null
{
    /system/bin/getprop ro.zygote
    /system/bin/getprop ro.product.cpu.abilist32
    /system/bin/getprop ro.product.cpu.abilist64
    /system/bin/getprop ro.vndk.version
    /system/bin/getprop apexd.status
    /system/bin/ls -l /system/bin/boringssl_self_test32 /system/bin/boringssl_self_test64
    /system/bin/ls -l /apex/com.android.conscrypt/bin/boringssl_self_test32 /apex/com.android.conscrypt/bin/boringssl_self_test64
} > /data/g9650-debug/environment.txt 2>&1
/system/bin/chown 0:2000 /data/g9650-debug/environment.txt
/system/bin/chmod 0640 /data/g9650-debug/environment.txt
wait "$g9650_log_pid"
