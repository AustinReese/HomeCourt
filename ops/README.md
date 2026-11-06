## ops

OS-level config for the Raspberry Pi that runs HomeCourt. Install or re-apply with:

```
sudo ~/HomeCourt/ops/install.sh
```

| File | Installed to | Why |
|---|---|---|
| `system/10-watchdog.conf` | `/etc/systemd/system.conf.d/` | Arms the 15s hardware watchdog while running and during reboots. A reboot hang on 2026-10-25 left the box dead for 9h because systemd's 10min default is beyond the BCM2835's 15s limit, so no watchdog was ever armed. |
| `system/90-panic-reboot.conf` | `/etc/sysctl.d/` | Reboot automatically after a kernel panic or oops instead of sitting frozen. |
| `system/dhcpcd.exit-hook` | `/etc/dhcpcd.exit-hook` | Keeps Wi-Fi power save off; it caused several disconnects a day. |
| `noipv4ll` line | `/etc/dhcpcd.conf` | Stops dhcpcd deleting the default route after a Wi-Fi blip, which cut the scoreboards off from ESPN for hours. |
| `system/journald-size.conf` | `/etc/systemd/journald.conf.d/` | Caps the persistent journal at 300M. |
| `system/docker-daemon.json` | `/etc/docker/daemon.json` | Rotates container logs (only if no daemon.json exists yet). |
| `isolcpus=3` | `/boot/cmdline.txt` | rpi-rgb-led-matrix's recommendation: gives the LED refresh thread its own core. Must be on the file's single line. |
| `homecourt-health.sh` + `systemd/homecourt-health.*` | `/usr/local/bin/`, `/etc/systemd/system/` | Every 2 minutes: re-joins Wi-Fi if the gateway stops answering (reboots after ~20 min down), restarts `pi-api`/`pi-ui` if they stop answering HTTP, logs power throttling and a nearly full disk. See `journalctl -u homecourt-health`. |
| `systemd/pi-*.service` | `/etc/systemd/system/` | The app units, versioned here. |

The installer also removes the old weekly `shutdown -r` from root's crontab. Scheduled reboots are a regular chance for a reboot hang, and nothing here depends on them.
