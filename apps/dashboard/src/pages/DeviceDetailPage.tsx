import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import type { DeviceDetail, Group } from "../types";
import {
  Button,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  PanelHeader,
  inputClass,
} from "../components/layout";
import { PlatformTag, QualityTag, Stat } from "../components/ui";
import { ChartLegend, UsageChart } from "../components/UsageChart";
import { formatBytes, formatDate, relativeTime } from "../lib/format";

export function DeviceDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const device = useApi<DeviceDetail>(() => api.device(id), [id], { pollMs: 30000 });
  const groups = useApi<Group[]>(() => api.groups());
  const usage = useApi(() => api.deviceUsage(id), [id]);
  const [name, setName] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  if (device.loading && !device.data) return <Loading label="Loading device…" />;
  if (device.error && !device.data)
    return <ErrorBox message={device.error} onRetry={device.refresh} />;
  const d = device.data!;

  const scopeNote: Record<string, string> = {
    device_total: "Counts whole-device traffic on the selected physical interfaces.",
    all_interfaces: "Counts every network interface except loopback.",
    android_total: "Android TrafficStats device totals; may include mobile and metered data.",
    interface: "Counts a single named interface.",
    app_only: "iOS can only reliably count this app's own URLSession traffic.",
    partial: "Only part of this device's traffic can be measured.",
    unsupported: "No reliable device-wide counter is available on this platform.",
  };

  async function save() {
    setSaving(true);
    setNotice(null);
    try {
      await api.patchDevice(id, { name: name ?? d.name });
      await device.refresh();
      setNotice("Saved.");
      setName(null);
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function changeGroup(groupId: string) {
    setNotice(null);
    try {
      await api.patchDevice(id, { group_id: groupId || null });
      await device.refresh();
      await usage.refresh();
      setNotice("Group updated. Historical usage stays attributed to the previous group.");
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Update failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={d.name}
        description={d.group_name ? `Member of ${d.group_name}` : "Not assigned to a group"}
        actions={
          <Button variant="ghost" onClick={() => navigate("/devices")}>
            Back to devices
          </Button>
        }
      />

      {notice && (
        <p className="rounded-card border border-line bg-surface px-4 py-2 text-sm text-muted">
          {notice}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="This period (down)" value={formatBytes(d.current_period_received)} />
        <Stat label="This period (up)" value={formatBytes(d.current_period_sent)} />
        <Stat
          label="Last report"
          value={<span className="text-2xl">{relativeTime(d.last_seen_at)}</span>}
          sub={d.is_stale ? "Stale" : "Current"}
          tone={d.is_stale ? "warn" : "default"}
        />
        <Stat
          label="Sequence"
          value={d.last_sequence}
          sub="Highest accepted sample"
        />
      </div>

      <Panel>
        <PanelHeader title="Usage this period" />
        <div className="px-4 py-4 sm:px-5">
          <div className="mb-3">
            <ChartLegend />
          </div>
          {usage.data ? (
            <UsageChart series={usage.data.series} />
          ) : (
            <Loading label="Loading usage…" />
          )}
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Manage" />
          <div className="space-y-4 px-4 py-4 sm:px-5">
            <div className="flex items-end gap-2">
              <label className="flex-1">
                <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
                  Name
                </span>
                <input
                  value={name ?? d.name}
                  onChange={(e) => setName(e.target.value)}
                  className={inputClass}
                />
              </label>
              <Button onClick={save} disabled={saving || name === null}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
            <label className="block">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
                Group
              </span>
              <select
                value={d.group_id ?? ""}
                onChange={(e) => changeGroup(e.target.value)}
                className={inputClass}
              >
                <option value="">Unassigned</option>
                {(groups.data ?? []).map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </label>
            {d.is_active ? (
              <Button
                variant="danger"
                onClick={async () => {
                  if (!confirm(`Revoke ${d.name}? Its credential will stop working.`))
                    return;
                  await api.revokeDevice(id);
                  await device.refresh();
                }}
              >
                Revoke device
              </Button>
            ) : (
              <p className="text-sm text-danger">
                This device has been revoked. Re-enroll it to restore access.
              </p>
            )}
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Measurement" />
          <dl className="space-y-3 px-4 py-4 text-sm sm:px-5">
            <Row label="Platform">
              <PlatformTag platform={d.platform} />
            </Row>
            <Row label="Agent version">{d.agent_version ?? "—"}</Row>
            <Row label="Scope">
              <span className="font-mono text-xs">{d.measurement_scope}</span>
            </Row>
            <Row label="Quality">
              <QualityTag quality={d.measurement_quality} scope={d.measurement_scope} />
              {d.measurement_quality === "exact" && (
                <span className="text-muted">Full coverage</span>
              )}
            </Row>
            <Row label="Enrolled">{formatDate(d.created_at)}</Row>
            <Row label="Interfaces">
              <span className="font-mono text-xs">
                {d.interfaces.length ? d.interfaces.join(", ") : "—"}
              </span>
            </Row>
          </dl>
          <p className="border-t border-line px-4 py-3 text-xs text-muted sm:px-5">
            {scopeNote[d.measurement_scope] ??
              "Measurement scope is reported by the agent."}
          </p>
          {d.recent_warnings.length > 0 && (
            <ul className="border-t border-line px-4 py-3 text-xs text-warn sm:px-5">
              {d.recent_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="flex items-center gap-2 text-right">{children}</dd>
    </div>
  );
}