"""Desktop agent entrypoint.

Usage:
    netquota-agent enroll --server URL --code CODE --name NAME
    netquota-agent run
    netquota-agent once
    netquota-agent status
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from . import __version__
from .collector import collect
from .config import AgentConfig, platform_name, credential_path
from .credentials import load_credential
from .enrollment import enroll, load_credential_for_state
from .reporter import ApiClient, ApiError
from .state import AgentState


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def report_once(client: ApiClient, state: AgentState, config: AgentConfig) -> bool:
    collected = collect(
        policy=config.interface_policy,
        include=config.include_interfaces,
        exclude=config.exclude_interfaces,
    )
    sequence = state.next_sequence()
    payload = {
        "schema_version": 1,
        "sequence": sequence,
        "observed_at": _iso_now(),
        "measurement_scope": collected.measurement_scope,
        "measurement_quality": collected.measurement_quality,
        "interfaces": [
            {
                "name": i.name,
                "bytes_received_total": i.bytes_received_total,
                "bytes_sent_total": i.bytes_sent_total,
            }
            for i in collected.interfaces
        ],
    }
    try:
        result = client.report_usage(payload)
    except ApiError as exc:
        # Do not advance the persisted sequence on failure so the next attempt
        # reuses it (server-side idempotency makes retries safe).
        state.sequence -= 1
        state.last_report_ok = False
        state.last_error = str(exc)
        state.save()
        return False

    state.last_report_at = _iso_now()
    state.last_report_ok = True
    state.last_error = None
    state.counters = {i.name: [i.bytes_received_total, i.bytes_sent_total] for i in collected.interfaces}
    state.save()
    return True


def cmd_enroll(args) -> int:
    config = AgentConfig.load()
    server = args.server or config.server_url
    try:
        state = enroll(server_url=server, enrollment_code=args.code, name=args.name, config=config)
    except ApiError as exc:
        print(f"enrollment failed: {exc}", file=sys.stderr)
        return 1
    config.server_url = server
    config.save()
    print(f"Enrolled device {state.device_id} ({platform_name()}).")
    print(f"Credential stored at {credential_path()} (or OS keyring).")
    return 0


def _build_client() -> tuple[ApiClient, AgentState, AgentConfig] | None:
    config = AgentConfig.load()
    state = AgentState.load()
    if not state.device_id:
        print("Not enrolled. Run: netquota-agent enroll ...", file=sys.stderr)
        return None
    credential = load_credential_for_state(state)
    if not credential:
        print("Credential missing. Re-enroll this device.", file=sys.stderr)
        return None
    client = ApiClient(
        config.server_url,
        device_id=state.device_id,
        credential=credential,
        verify_tls=config.verify_tls,
    )
    return client, state, config


def cmd_once(_args) -> int:
    built = _build_client()
    if not built:
        return 1
    client, state, config = built
    ok = report_once(client, state, config)
    print("reported" if ok else f"report failed: {state.last_error}")
    return 0 if ok else 1


def cmd_run(_args) -> int:
    built = _build_client()
    if not built:
        return 1
    client, state, config = built
    print(f"NetQuota agent {__version__} running; interval={config.interval_seconds}s")
    while True:
        report_once(client, state, config)
        time.sleep(max(30, config.interval_seconds))


def cmd_status(_args) -> int:
    config = AgentConfig.load()
    state = AgentState.load()
    print(json.dumps(
        {
            "version": __version__,
            "platform": platform_name(),
            "server_url": config.server_url,
            "device_id": state.device_id,
            "sequence": state.sequence,
            "last_report_at": state.last_report_at,
            "last_report_ok": state.last_report_ok,
            "last_error": state.last_error,
            "interval_seconds": config.interval_seconds,
            "interface_policy": config.interface_policy,
            "credential_present": bool(load_credential_for_state(state)),
        },
        indent=2,
    ))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="netquota-agent", description="NetQuota desktop agent")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_enroll = sub.add_parser("enroll", help="enroll this device")
    p_enroll.add_argument("--server", default=None)
    p_enroll.add_argument("--code", required=True)
    p_enroll.add_argument("--name", required=True)
    p_enroll.set_defaults(func=cmd_enroll)

    sub.add_parser("run", help="run continuously").set_defaults(func=cmd_run)
    sub.add_parser("once", help="report once").set_defaults(func=cmd_once)
    sub.add_parser("status", help="show status").set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())