# Platform limitations and verification status

This document records exactly what each platform can measure with **public,
supported APIs**, and what has actually been verified versus written against the
docs. Nothing here is a promise that has not been tested.

## Summary

| Platform | Whole-device bytes | Method | Verified in this repo? |
|----------|--------------------|--------|------------------------|
| Windows | Yes | `psutil.net_io_counters(pernic=True)` | Collector unit-tested; interface policy verified. Not run on this Windows host end-to-end (agent is platform-independent and its selection tests pass). |
| Linux | Yes | `psutil.net_io_counters(pernic=True)` | Collector unit-tested. Not run on a Linux host in this environment. |
| Android | Device totals (since boot) | `android.net.TrafficStats` | Source written against public API. **Not built** (no Android SDK here); unit tests provided for pure logic. |
| iOS | **No** | none available | Source written against public API. **Not compiled** (no Xcode here). |

## Windows and Linux

- Counters come from `psutil.net_io_counters(pernic=True)`: cumulative bytes per
  interface since boot/reset.
- **Interface selection** (the reason this matters): summing every interface
  double counts traffic that passes through bridges, virtual switches, VPN
  tunnels, or container networks. The default `primary` policy counts only
  physical interfaces (`Ethernet`, `Wi-Fi`, `eth0`, `wlan0`, `enp*`, `wlp*`, …)
  and excludes loopback and known virtual prefixes (`docker`, `br-`, `veth`,
  `virbr`, `vmnet`, `vboxnet`, `tun`, `tap`, `wg`, `utun`, `vEthernet`,
  `Loopback`, `Bluetooth`, ...).
- Operators can override with `include_interfaces` / `exclude_interfaces` in the
  agent config, or set the policy to `all`.
- Counters reset on reboot or adapter reset. The agent persists its sequence so
  ordering survives restarts; the server treats a lower counter as a reset and
  re-baselines instead of producing a bogus delta.
- Wi-Fi vs Ethernet: if a device uses both, both physical interfaces are counted,
  which is correct (distinct traffic). If a VPN is active, its tunnel interface is
  excluded, avoiding double counting of the same bytes.

**Not verified:** end-to-end operation on a real Windows machine and real Linux
distributions. The portable logic is unit-tested; peristalsis of `psutil` counters
across a real sleep/reboot cycle should be confirmed on target hardware before
calling the platform "fully supported" (see the checklist).

## Android

- `TrafficStats.getTotalRxBytes()` / `getTotalTxBytes()` return **device-wide**
  cumulative byte totals since boot, across mobile and Wi-Fi, and require no
  permission. These are the counters the agent reports (`android_total`).
- `getMobileRxBytes()` / `getMobileTxBytes()` are included for visibility but the
  server's `primary` policy counts only the `total` interface, avoiding double
  counting.
- **Reset on reboot**: since-boot counters restart at every reboot. This is
  reported and handled as a reset by the server.
- **Background execution**: reporting uses `WorkManager` with a 15-minute minimum
  interval and a network constraint. Android batches and defers background work
  and applies battery optimizations; **reporting is not real-time** and can be
  delayed or skipped. The UI states this rather than promising live updates.
- **Per-app usage** is not collected; only device totals are reported.
- A legacy per-UID API (`TrafficStats.getUidRxBytes`) is unreliable on modern
  Android and is deliberately not used.

**Not verified:** the app has not been compiled or run on an emulator/device in
this environment (no Android SDK/Gradle available here). Compile with Android
Studio (Gradle 8.5+, JDK 17) and run the provided unit tests.

## iOS — the important limitation

Ordinary iOS applications **cannot** read whole-device network byte counters with
public APIs, and cannot run an unrestricted background monitoring service.

- `NWPathMonitor` reports connectivity, not byte counts.
- `getifaddrs` on iOS does not reliably expose `if_data` byte totals for other
  interfaces to sandboxed apps, and using it that way is not a supported public
  interface for this purpose.
- `URLSession` / `URLSessionTaskMetrics` reports bytes for requests **this app
  makes** — not the device.
- Whole-device observation requires a **Network Extension** (packet tunnel /
  `NEFilterDataProvider`), the Network Extension entitlement, and presents to the
  user as a VPN. This project deliberately does **not** use packet interception or
  an undeclared VPN to work around the limitation.

Consequences for NetQuota on iPhone:

- The agent reports **`app_only` / `partial`** measurement. If the app makes no
  network requests, there is nothing meaningful to report.
- iPhone figures are **not comparable** to Windows/Linux/Android device-wide
  totals, and the dashboard surfaces a measurement warning.
- Background reporting uses `BGAppRefreshTask`. iOS schedules these
  opportunistically with **no guaranteed interval**; reports may be delayed or
  never run. Web-app/dashboard usage is unaffected.
- Enrollment, device metadata, connection status, last successful report, and
  the data-collection explanation all work and are shown in-app.

What NetQuota does **not** do on iOS: fabricate usage, present partial
measurements as whole-device totals, or claim iPhone monitoring equals
Windows/Linux.

**Not verified:** iOS target not compiled here (no Xcode). Written against public
iOS 16 APIs; build with XcodeGen (see `apps/ios-agent/README.md`).

## Accounting limitations (all platforms)

- Totals are **device-reported usage**, not guaranteed ISP-billed usage.
- If an agent is offline, its traffic for that window is simply not measured; the
  dashboard flags stale devices rather than inventing numbers.
- If a device changes group, usage is attributed to the group active at record
  time; history is preserved.
- Alerting only. NetQuota never blocks, throttles, or disconnects.

## Synthetic (demo) data

The simulator and `seed_demo.py` create devices with `platform="simulator"` and a
`[SIM]` name prefix. This data is always visually distinguishable in the
dashboard (a "Simulated" tag) and can be disabled by not running the simulator.