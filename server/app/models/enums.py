"""Value constants shared across models and services (stored as strings)."""

from __future__ import annotations


class Platform:
    WINDOWS = "windows"
    LINUX = "linux"
    ANDROID = "android"
    IOS = "ios"
    SIMULATOR = "simulator"
    UNKNOWN = "unknown"

    ALL = {WINDOWS, LINUX, ANDROID, IOS, SIMULATOR, UNKNOWN}


class MeasurementScope:
    """What a cumulative counter actually measures."""

    DEVICE_TOTAL = "device_total"  # whole-device bytes (Windows/Linux primary iface)
    ALL_INTERFACES = "all_interfaces"  # summed physical interfaces
    ANDROID_TOTAL = "android_total"  # TrafficStats device totals (incl. mobile+metered)
    INTERFACE = "interface"
    APP_ONLY = "app_only"  # only this app's bytes (iOS URLSession)
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"

    ALL = {
        DEVICE_TOTAL,
        ALL_INTERFACES,
        ANDROID_TOTAL,
        INTERFACE,
        APP_ONLY,
        PARTIAL,
        UNSUPPORTED,
        UNKNOWN,
    }


class MeasurementQuality:
    """Confidence in a device-reported counter."""

    EXACT = "exact"
    ESTIMATED = "estimated"
    PARTIAL = "partial"
    UNKNOWN = "unknown"

    ALL = {EXACT, ESTIMATED, PARTIAL, UNKNOWN}


class EventType:
    THRESHOLD_80 = "threshold_80"
    THRESHOLD_90 = "threshold_90"
    THRESHOLD_100 = "threshold_100"
    QUOTA_RESET = "quota_reset"
    STALE_AGENT = "stale_agent"
    AGENT_RECOVERED = "agent_recovered"
    ENROLLMENT_CREATED = "enrollment_created"
    ENROLLMENT_USED = "enrollment_used"
    DEVICE_REVOKED = "device_revoked"
    DEVICE_ACTIVATED = "device_activated"
    GROUP_CHANGED = "group_changed"
    QUOTA_PERIOD_CREATED = "quota_period_created"
    QUOTA_CORRECTION = "quota_correction"
    ACCOUNTING_WARNING = "accounting_warning"
    COUNTER_RESET = "counter_reset"
    SERVER_STARTED = "server_started"

    ALL = {
        THRESHOLD_80,
        THRESHOLD_90,
        THRESHOLD_100,
        QUOTA_RESET,
        STALE_AGENT,
        AGENT_RECOVERED,
        ENROLLMENT_CREATED,
        ENROLLMENT_USED,
        DEVICE_REVOKED,
        DEVICE_ACTIVATED,
        GROUP_CHANGED,
        QUOTA_PERIOD_CREATED,
        QUOTA_CORRECTION,
        ACCOUNTING_WARNING,
        COUNTER_RESET,
        SERVER_STARTED,
    }


THRESHOLDS = (80, 90, 100)