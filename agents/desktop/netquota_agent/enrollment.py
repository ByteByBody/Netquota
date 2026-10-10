"""Enrollment helper for the desktop agent."""

from __future__ import annotations

import uuid

from .config import AgentConfig, platform_name
from .collector import collect
from .credentials import store_credential
from .reporter import ApiClient, ApiError
from .state import AgentState


def ensure_installation_id(state: AgentState) -> str:
    if not state.installation_id:
        state.installation_id = str(uuid.uuid4())
    return state.installation_id


def enroll(
    *,
    server_url: str,
    enrollment_code: str,
    name: str,
    config: AgentConfig | None = None,
    state: AgentState | None = None,
) -> AgentState:
    """Enroll this device and persist the returned credential and device id."""
    config = config or AgentConfig.load()
    state = state or AgentState.load()
    client = ApiClient(server_url, verify_tls=config.verify_tls)

    collected = collect(
        policy=config.interface_policy,
        include=config.include_interfaces,
        exclude=config.exclude_interfaces,
    )
    result = client.enroll(
        enrollment_code=enrollment_code,
        name=name,
        platform=platform_name(),
        measurement_scope=collected.measurement_scope,
        measurement_quality=collected.measurement_quality,
        capabilities={"collector": "psutil", "interfaces": [i.name for i in collected.interfaces]},
        installation_id=ensure_installation_id(state),
    )
    device_id = result["device_id"]
    credential = result["credential"]
    store_credential(device_id, credential)

    state.device_id = device_id
    state.sequence = 0
    state.save()
    return state


def load_credential_for_state(state: AgentState) -> str | None:
    from .credentials import load_credential

    if not state.device_id:
        return None
    return load_credential(state.device_id)