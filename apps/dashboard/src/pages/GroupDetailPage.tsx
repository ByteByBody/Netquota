import { useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import type { Device, GroupUsage, EventItem } from "../types";
import {
  Button,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  PanelHeader,
  inputClass,
} from "../components/layout";
import { PlatformTag, QualityTag, QuotaMeter, SeverityDot, Stat } from "../components/ui";
import { ChartLegend, UsageChart } from "../components/UsageChart";
import { formatBytes, formatDate, parseGib, relativeTime } from "../lib/format";

export function GroupDetailPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const usage = useApi<GroupUsage>(() => api.groupUsage(id), [id], { pollMs: 30000 });
  const devices = useApi<Device[]>(() => api.devices());
  const events = useApi<EventItem[]>(() => api.events({ group_id: id }), [id]);
  const [quotaInput, setQuotaInput] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  if (usage.loading && !usage.data) return <Loading label="Loading group…" />;
  if (usage.error && !usage.data)
    return <ErrorBox message={usage.error} onRetry={usage.refresh} />;
  const { summary, series } = usage.data!;

  const members = (devices.data ?? []).filter((d) => d.group_id === id);
  const candidates = (devices.data ?? []).filter((d) => d.group_id !== id);

  async function applyQuota() {
    const bytes = parseGib(quotaInput);
    if (bytes <= 0) {
      setNotice("Enter a quota such as “10” or “500 MiB”.");
      return;
    }
    try {
      await api.patchGroup(id, { quota_bytes: bytes });
      setQuotaInput("");
      setNotice("Quota updated for the current period.");
      await usage.refresh();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "Update failed");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={summary.group_name}
        description={
          summary.period_starts_at
            ? `Period ${formatDate(summary.period_starts_at)} – ${formatDate(summary.period_ends_at)}`
            : "No active period"
        }
        actions={
          <Button variant="ghost" onClick={() => navigate("/groups")}>
            Back to groups
          </Button>
        }
      />

      {notice && (
        <p className="rounded-card border border-line bg-surface px-4 py-2 text-sm text-muted">
          {notice}
        </p>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Used" value={formatBytes(summary.used_bytes)} />
        <Stat label="Remaining" value={formatBytes(summary.remaining_bytes)} />
        <Stat
          label="Consumed"
          value={`${summary.percentage_used.toFixed(1)}%`}
          tone={
            summary.percentage_used >= 100
              ? "danger"
              : summary.percentage_used >= 80
                ? "warn"
                : "default"
          }
        />
        <Stat
          label="Devices"
          value={summary.device_count}
          sub={summary.has_missing_measurements ? "Some partial coverage" : "Full coverage"}
        />
      </div>

      <Panel>
        <PanelHeader title="Quota" />
        <div className="px-4 py-4 sm:px-5">
          <QuotaMeter
            used={summary.used_bytes}
            quota={summary.quota_bytes}
            percentage={summary.percentage_used}
          />
          <div className="mt-4 flex items-end gap-2">
            <label className="flex-1">
              <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">
                Set monthly quota
              </span>
              <input
                value={quotaInput}
                onChange={(e) => setQuotaInput(e.target.value)}
                placeholder={`Current ${formatBytes(summary.quota_bytes)}`}
                className={inputClass}
              />
            </label>
            <Button onClick={applyQuota} disabled={!quotaInput.trim()}>
              Update
            </Button>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Daily usage" />
        <div className="px-4 py-4 sm:px-5">
          <div className="mb-3">
            <ChartLegend />
          </div>
          <UsageChart series={series} />
        </div>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title={`Devices (${members.length})`} />
          {members.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted sm:px-5">
              No devices in this group yet.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {members.map((d) => (
                <li
                  key={d.id}
                  className="flex items-center justify-between gap-3 px-4 py-3 text-sm sm:px-5"
                >
                  <div>
                    <Link to={`/devices/${d.id}`} className="font-medium hover:text-signal">
                      {d.name}
                    </Link>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-muted">
                      <PlatformTag platform={d.platform} />
                      <QualityTag quality={d.measurement_quality} scope={d.measurement_scope} />
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    onClick={async () => {
                      await api.patchDevice(d.id, { group_id: null });
                      await usage.refresh();
                      await devices.refresh();
                    }}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {candidates.length > 0 && (
            <div className="border-t border-line px-4 py-3 sm:px-5">
              <label className="block text-xs font-medium uppercase tracking-wide text-muted">
                Add a device
              </label>
              <select
                value=""
                onChange={async (e) => {
                  if (!e.target.value) return;
                  await api.assignDevice(id, e.target.value);
                  await usage.refresh();
                  await devices.refresh();
                }}
                className={`${inputClass} mt-1`}
              >
                <option value="">Select device…</option>
                {candidates.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.platform})
                  </option>
                ))}
              </select>
            </div>
          )}
        </Panel>

        <Panel>
          <PanelHeader title="Threshold events" />
          {(events.data ?? []).filter((e) => e.event_type.startsWith("threshold_"))
            .length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted sm:px-5">
              No quota thresholds reached in this group yet.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {(events.data ?? [])
                .filter((e) => e.event_type.startsWith("threshold_") || e.event_type === "counter_reset")
                .map((e) => (
                  <li key={e.id} className="flex items-start gap-3 px-4 py-3 text-sm sm:px-5">
                    <span className="mt-1.5">
                      <SeverityDot severity={e.severity} />
                    </span>
                    <div>
                      <p>{e.message ?? e.event_type}</p>
                      <p className="tnum text-xs text-faint">
                        {e.event_type} · {relativeTime(e.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}