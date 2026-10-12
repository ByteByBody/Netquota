"""Tests for the keep-alive supervisor decision logic."""

from netquota_launcher.plan import Component
from netquota_launcher.supervisor import Supervisor


def _comp(name):
    return Component(name=name, kind=name, cwd=".", argv=["x"])


def test_ensure_starts_missing_components():
    started = []
    sup = Supervisor(
        [_comp("agent")], is_up=lambda c: False, start=lambda c: started.append(c.name)
    )
    assert sup.ensure_once() == ["agent"]
    assert started == ["agent"]


def test_ensure_leaves_running_components_alone():
    started = []
    sup = Supervisor(
        [_comp("agent")], is_up=lambda c: True, start=lambda c: started.append(c.name)
    )
    assert sup.ensure_once() == []
    assert started == []


def test_ensure_respects_cooldown_between_restart_attempts():
    now = [100.0]
    started = []
    sup = Supervisor(
        [_comp("agent")],
        is_up=lambda c: False,
        start=lambda c: started.append(c.name),
        cooldown=15.0,
        clock=lambda: now[0],
    )
    assert sup.ensure_once() == ["agent"]
    assert sup.ensure_once() == []  # still cooling down
    now[0] += 16.0
    assert sup.ensure_once() == ["agent"]
    assert started == ["agent", "agent"]


def test_run_loops_until_stop_is_requested():
    ticks = []
    stop = [False]

    def stop_requested():
        return stop[0]

    def sleep(_seconds):
        ticks.append(1)
        stop[0] = True  # request stop after the first wait

    sup = Supervisor([_comp("agent")], is_up=lambda c: True, start=lambda c: None)
    sup.run(stop_requested=stop_requested, sleep=sleep, poll_seconds=3.0)
    assert ticks == [1]
