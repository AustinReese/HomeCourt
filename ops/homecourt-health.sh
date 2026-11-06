#!/bin/bash
# HomeCourt health check, run every 2 minutes by homecourt-health.timer.
# Recovers from failures that leave the box up but unreachable: Wi-Fi that
# stops passing traffic, and app services that are running but not answering.
# Output goes to the journal: journalctl -u homecourt-health
set -u

STATE=/run/homecourt-health
mkdir -p "$STATE"

# Consecutive-failure counters live in /run, so a reboot resets them
bump() { local n=$(( $(cat "$STATE/$1" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE/$1"; echo "$n"; }
clear_count() { rm -f "$STATE/$1"; }

uptime_seconds=$(cut -d. -f1 /proc/uptime)

# --- Network: the default gateway must answer. A missing default route counts
# as a failure too (dhcpcd has dropped it after Wi-Fi blips before).
gateway=$(ip route show default | awk '/^default/ {print $3; exit}')
if [ -n "$gateway" ] && ping -c 3 -W 2 -q "$gateway" >/dev/null 2>&1; then
    clear_count network
else
    n=$(bump network)
    echo "gateway ${gateway:-<no default route>} unreachable ($n consecutive checks)"
    # ~20 minutes down: reboot, but never within 30 minutes of boot so a dead
    # router can't put the Pi into a reboot loop
    if [ "$n" -ge 10 ] && [ "$uptime_seconds" -ge 1800 ]; then
        echo "network down for ~20 minutes, rebooting"
        systemctl reboot
        exit 0
    elif [ "$n" -ge 3 ]; then
        echo "reassociating wlan0 and rebinding DHCP"
        /sbin/wpa_cli -i wlan0 reassociate >/dev/null 2>&1
        /sbin/dhcpcd -n wlan0 >/dev/null 2>&1
    fi
fi

# --- App services: any HTTP response (even a 404) means the server is alive.
# Restart after two consecutive misses so a normal restart window isn't punished.
check_http() {
    local unit=$1 url=$2
    if curl -s -o /dev/null -m 10 "$url"; then
        clear_count "$unit"
        return
    fi
    local n
    n=$(bump "$unit")
    echo "$unit not answering at $url ($n consecutive checks)"
    if [ "$n" -ge 2 ] && [ "$uptime_seconds" -ge 300 ]; then
        echo "restarting $unit"
        systemctl restart "$unit"
        clear_count "$unit"
    fi
}
check_http pi-api http://127.0.0.1:8080/
check_http pi-ui http://127.0.0.1:80/

# --- Power: log throttling flags when they change. Bit 0 = under-voltage now,
# bit 16 = under-voltage has occurred since boot.
throttled=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
if [ -n "$throttled" ] && [ "$throttled" != "$(cat "$STATE/throttled" 2>/dev/null)" ]; then
    echo "$throttled" > "$STATE/throttled"
    [ "$throttled" != "0x0" ] && echo "power/thermal throttling flags: throttled=$throttled"
fi

# --- Disk: warn before the SD card fills up
root_use=$(df --output=pcent / | tail -1 | tr -dc '0-9')
if [ "${root_use:-0}" -ge 90 ]; then
    echo "root filesystem ${root_use}% full"
fi

exit 0
