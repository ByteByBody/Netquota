# NetQuota: Home-Network Scoped Counting

By default NetQuota counts **everything** a device transfers on its selected
interfaces. Some households instead want to count **only the portion that
happened while the device was on their own network** (e.g. exclude a laptop's
hotel-Wi-Fi or mobile-hotspot usage).

This document explains the feature, how to enable it, and its honest
limitations.

---

## What it does

When enabled, the agent keeps its own **accumulated** counter per interface. It
samples the raw OS counters every `sample_seconds` (default 30 s), checks
whether the current default gateway's MAC matches a configured allow-list, and
**only adds the interval's delta to the accumulated total if the *previous*
sample was on your network**.

- Joining your network: the first on-network sample **does not** count pre-join
  bytes (the interval that brought you home is skipped).
- Leaving your network: the last on-network interval **is** counted (safer to
  over- than under-count).
- The server sees an ordinary monotonic counter (`estimated` quality) and
  applies its existing delta/reset/idempotency logic — no server change needed.

The reported `measurement_quality` is `estimated`, and a note is attached so
the dashboard never overclaims it as an exact ISP-billed total.

---

## Prerequisites

- Your router's LAN MAC address (the MAC of the default gateway the device
  sees). This is the most stable identifier — it works for both Wi-Fi and
  Ethernet, and survives IP changes.
- The device must be able to read its own ARP table (standard on Windows/Linux).

---

## Enable on the full desktop agent (Windows/Linux)

```sh
# 1. Detect your gateway MAC
netquota-agent detect-gateway
# Example output: "Default gateway MAC: 64:6d:6c:96:e0:b7"

# 2. Enable home-network counting with that MAC
netquota-agent set-gateway 64:6d:6c:96:e0:b7

# 3. Run normally
netquota-agent run
```

To disable later:

```sh
netquota-agent scope-off
```

### Manual config

The same can be done by editing the agent config file
(`%ProgramData%\NetQuota\agent.json` on Windows,
`~/.config/netquota/agent.json` on Linux):

```json
{
  "count_scope": "home_network",
  "gateway_macs": ["64:6d:6c:96:e0:b7"],
  "sample_seconds": 30
}
```

You can list multiple MACs if your device sometimes roams between APs with
different gateway MACs.

### See what would be reported (no server call)

```sh
netquota-agent sample
```

---

## Enable on routers / NAS / Pi (no psutil, no pip)

Use the standalone `netquota-lite.py` script — a single file, stdlib only,
reads `/proc/net/dev`. Works on OpenWrt, Debian, Alpine, Synology, QNAP,
Raspberry Pi OS, etc.

```sh
# Copy the script to the device
scp netquota-lite.py root@router:/opt/netquota/

# Run once to test
python3 /opt/netquota/netquota-lite.py \
  --server https://netquota.local \
  --device-id <UUID> \
  --credential <TOKEN> \
  --gateway-mac aa:bb:cc:dd:ee:ff \
  --once
```

For persistent operation, install it as a service:

**OpenWrt (`/etc/init.d/netquota-lite`):**

```sh
#!/bin/sh /etc/rc.common
START=99
STOP=10
USE_PROCD=1

start_service() {
    procd_open_instance
    procd_set_param command python3 /opt/netquota/netquota-lite.py \
        --server https://netquota.local \
        --device-id YOUR_DEVICE_ID \
        --credential YOUR_CREDENTIAL \
        --gateway-mac aa:bb:cc:dd:ee:ff \
        --interval 300
    procd_set_param respawn
    procd_close_instance
}
```

**systemd (Debian/Alpine/Pi):**

```ini
# /etc/systemd/system/netquota-lite.service
[Unit]
Description=NetQuota Lite reporter
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/netquota/netquota-lite.py \
    --server https://netquota.local \
    --device-id YOUR_DEVICE_ID \
    --credential YOUR_CREDENTIAL \
    --gateway-mac aa:bb:cc:dd:ee:ff \
    --interval 300
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Honest limitations

| Limitation | What it means |
|---|---|
| **Sampling resolution** | Only the *previous* sample's network is known. Switching networks mid-interval misattributes up to one interval's traffic (default 30 s). |
| **VPN on the device** | A device-side VPN tunnels bytes through one interface; the gateway MAC check still works, but *which* traffic went through the VPN vs. local LAN is invisible to the script. |
| **Counter resets** | OS counters reset on reboot/adapter reset. The script detects this (delta would go negative) and clamps to zero, but bytes sent *during* the reset are lost. |
| **No per-app breakdown** | The script measures interface totals only. |
| **iOS** | Cannot run scripts or background processes — this feature is unavailable on iPhone. |
| **Accuracy claim** | Quality is `estimated`. The dashboard shows a note and does **not** present this as exact ISP-billed usage. |

---

## Server side: no changes needed

The agent reports the same payload shape as before. The only differences:

- `measurement_quality`: `estimated` (instead of `exact`)
- `notes`: includes an explanation of the sampling resolution
- `measurement_scope`: still `device_total`

The server's accounting, quota, and alert logic is untouched.

---

## Quick checklist

- [ ] Find your router's LAN MAC (run `netquota-agent detect-gateway` on a machine on the LAN)
- [ ] `netquota-agent set-gateway <MAC>` on each machine you want scoped
- [ ] Verify with `netquota-agent sample` — interfaces should appear, quality = `estimated`
- [ ] For routers/NAS: copy `netquota-lite.py`, enroll a device for it, run with `--gateway-mac`
- [ ] Dashboard shows the device with an "estimated" badge and the note