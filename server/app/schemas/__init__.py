"""Pydantic schemas (API contracts)."""

from .agent import (
    AgentConfigOut,
    EnrollIn,
    EnrollOut,
    HeartbeatIn,
    HeartbeatOut,
    UsageReportIn,
    UsageReportOut,
    UsageInterfaceIn,
)
from .auth import AdminOut, LoginIn, TokenOut
from .dashboard import DashboardSummary, GroupQuotaSummary
from .devices import DeviceOut, DevicePatch, DeviceDetailOut
from .enrollment import (
    EnrollmentCodeCreate,
    EnrollmentCodeCreated,
    EnrollmentCodeOut,
)
from .events import EventOut
from .groups import (
    GroupCreate,
    GroupOut,
    GroupPatch,
    GroupUsageOut,
    GroupUsageSeries,
    UsagePoint,
)

__all__ = [
    "AgentConfigOut",
    "HeartbeatIn",
    "HeartbeatOut",
    "UsageReportIn",
    "UsageReportOut",
    "UsageInterfaceIn",
    "AdminOut",
    "LoginIn",
    "TokenOut",
    "DashboardSummary",
    "GroupQuotaSummary",
    "DeviceOut",
    "DevicePatch",
    "DeviceDetailOut",
    "EnrollIn",
    "EnrollOut",
    "EnrollmentCodeCreate",
    "EnrollmentCodeCreated",
    "EnrollmentCodeOut",
    "EventOut",
    "GroupCreate",
    "GroupOut",
    "GroupPatch",
    "GroupUsageOut",
    "GroupUsageSeries",
    "UsagePoint",
]