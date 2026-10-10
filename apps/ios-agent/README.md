# iOS agent

Native SwiftUI app that enrolls this iPhone with a NetQuota server and reports
the usage iOS actually lets a third-party app measure. It is honest about what
iOS cannot do.

## What this app measures

| Capability | Available? | Notes |
|------------|-----------|-------|
| Whole-device received/sent bytes | **No** | No public API. `NWPathMonitor`, `nw_*`, and BSD `getifaddrs` do not expose stable device-wide byte counters to sandboxed apps. |
| Per-interface byte counters | **No** | `getifaddrs` on iOS does not reliably provide `if_data` byte totals for other interfaces. |
| This app's own URLSession traffic | **Yes** | `URLSessionTaskMetrics` reports bytes per request. Reported as `app_only` / `partial`. |
| Whole-device totals without a VPN | **No** | `NEPacketTunnelProvider` / `NEFilterDataProvider` can observe traffic, but require the Network Extension (VPN) entitlement and present to the user as a VPN. This project deliberately does **not** use an undeclared VPN configuration. |

Because of this, NetQuota labels iPhone figures as **app-only / partial** and the
dashboard shows a measurement warning. iPhone usage is **not** comparable to
Windows, Linux, or Android device-wide totals.

## What still works on iPhone

- Enrollment with a single-use code and consent screen.
- Secure credential storage in the Keychain.
- Device metadata and status (last report, sequence, errors).
- Reporting the app's own measured traffic, where any exists.
- Pause / resume monitoring, and "forget this device".
- Background refresh where iOS grants it. iOS schedules `BGAppRefreshTask`
  opportunistically; there is **no guaranteed interval**, and reports may be
  delayed or skipped. The UI does not promise real-time reporting.

## Project layout

```
apps/ios-agent/
├── project.yml                 # XcodeGen spec (generates NetQuota.xcodeproj)
├── NetQuota/
│   ├── App/NetQuotaApp.swift
│   ├── Core/
│   │   ├── ApiClient.swift
│   │   ├── BackgroundScheduler.swift
│   │   ├── KeychainStore.swift
│   │   ├── MeasurementCollector.swift
│   │   └── Models.swift
│   ├── ViewModels/AgentViewModel.swift
│   ├── Views/ContentView.swift
│   ├── Resources/Info.plist
│   └── NetQuota.entitlements
└── NetQuotaTests/
```

## Build

Xcode is required (macOS). Generate the Xcode project with
[XcodeGen](https://github.com/yonaskolb/XcodeGen):

```sh
brew install xcodegen
cd apps/ios-agent
xcodegen generate       # creates NetQuota.xcodeproj
open NetQuota.xcodeproj
```

Set your development team in the target's Signing settings, then run on a
device or simulator (iOS 16+).

> This environment has no Xcode or Swift toolchain, so the iOS target has not
> been compiled here. The Swift is written against public iOS 16 APIs only.

## Tests

`NetQuotaTests` covers the pure logic (state transitions and the measurement
scope reported to the server). Run with `⌘U` in Xcode.