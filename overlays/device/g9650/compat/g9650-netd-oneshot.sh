#!/system/bin/sh
# Extend RestlessOS's existing BPF-less fallback to the new oneshot check.
# Keep the real test and fail every unrecognized failure. Do not change netd.
/system/bin/netd oneshot
g9650_status=$?
if [ "$g9650_status" = 254 ] &&
   [ "$(/system/bin/getprop ro.boot.bootloader)" = G9650ZCS9FVA4 ] &&
   [ "$(/system/bin/uname -r)" = 4.9.186-klabitV6.5 ] &&
   [ ! -e /sys/fs/bpf/netd_shared/prog_netd_skfilter_allowlist_xtbpf ]; then
    /system/bin/log -p w -t G9650Compat "netd oneshot ENOENT: legacy 4.9 BPF-less fallback; daemon remains unchanged"
    echo '<4>G9650Compat: netd1shot ENOENT with missing BPF program; using existing legacy daemon fallback' > /dev/kmsg
    exit 0
fi
exit "$g9650_status"
