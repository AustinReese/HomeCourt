#!/bin/bash
# Installs the Pi's OS-level config from this directory. Idempotent: safe to re-run.
#   sudo ~/HomeCourt/ops/install.sh
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "run as root: sudo $0" >&2
    exit 1
fi

cd "$(dirname "$0")"
reboot_needed=0

# Watchdog, kernel panic reboot, journal size cap
install -D -m 644 system/10-watchdog.conf /etc/systemd/system.conf.d/10-watchdog.conf
install -D -m 644 system/90-panic-reboot.conf /etc/sysctl.d/90-panic-reboot.conf
install -D -m 644 system/journald-size.conf /etc/systemd/journald.conf.d/50-size.conf

# Wi-Fi: power save off, and no IPv4LL fallback (dhcpcd 8.1.2 deletes the real
# default route when it tears the link-local address down)
install -m 644 system/dhcpcd.exit-hook /etc/dhcpcd.exit-hook
if ! grep -q '^noipv4ll' /etc/dhcpcd.conf; then
    printf '\n# IPv4LL fallback after a Wi-Fi blip makes dhcpcd delete the real default route\nnoipv4ll\n' >> /etc/dhcpcd.conf
fi

# Docker log rotation. Only applies to containers created after it is in place.
if [ ! -e /etc/docker/daemon.json ]; then
    install -D -m 644 system/docker-daemon.json /etc/docker/daemon.json
fi

# rpi-rgb-led-matrix recommends isolcpus=3 so its refresh thread gets a core to
# itself. The firmware only reads the first line of cmdline.txt, so it has to go there.
cmdline=$(head -n 1 /boot/cmdline.txt)
if [ "$(wc -l < /boot/cmdline.txt)" -gt 1 ] || [[ " $cmdline " != *" isolcpus=3 "* ]]; then
    cp -a /boot/cmdline.txt "/boot/cmdline.txt.bak-$(date +%Y%m%d%H%M%S)"
    [[ " $cmdline " == *" isolcpus=3 "* ]] || cmdline="$cmdline isolcpus=3"
    printf '%s\n' "$cmdline" > /boot/cmdline.txt.new
    mv /boot/cmdline.txt.new /boot/cmdline.txt
    reboot_needed=1
fi

# No scheduled reboots: a reboot that hangs is what took the box down on 2026-10-25
if crontab -l 2>/dev/null | grep -q 'shutdown -r'; then
    { crontab -l | grep -v 'shutdown -r' || true; } | crontab -
fi

# App units and the health check
install -m 644 systemd/pi-api.service systemd/pi-led.service systemd/pi-ui.service \
    systemd/homecourt-health.service systemd/homecourt-health.timer /etc/systemd/system/
install -m 755 homecourt-health.sh /usr/local/bin/homecourt-health

systemctl daemon-reload
systemctl daemon-reexec
sysctl -q -p /etc/sysctl.d/90-panic-reboot.conf
systemctl restart systemd-journald
/sbin/iw dev wlan0 set power_save off || true
systemctl enable --now homecourt-health.timer

echo "installed"
if [ "$reboot_needed" -eq 1 ]; then
    echo "cmdline.txt changed: reboot to apply isolcpus=3"
fi
