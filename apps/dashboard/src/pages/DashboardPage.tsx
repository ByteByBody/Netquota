import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import type { DashboardSummary } from "../types";
import { EmptyState, ErrorBox, Loading, PageHeader, Panel, PanelHeader } from "../components/layout";
import { QualityTag, QuotaMeter, SeverityDot, Stat } from "../components/ui";
import { ChartLegend, UsageChart } from "../components/UsageChart";
import { formatBytes, formatDate, relativeTime } from "../lib/format";

export function DashboardPage() {
  const { data, loading, error, refresh } = useApi<DashboardSummary>(
    () => api.summary(),
    [],
    { pollMs: 30000 },
  );
  const [showSeries, setShowSeries] = useState(true);

  if (loading && !data) return <Loading label="Reading meters…" />;
  if (error && !data) return <ErrorBox message={error} onRetry={refresh} />;
  if (!data) return null;

  const anyGroups = data.groups.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        description={
          data.active_period_starts_at
            ? `Current quota period started ${formatDate(data.active_period_starts_at)}.`
            : "No quota period is active yet."
        }
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat
          label="Devices"
          value={data.device_count}
          sub={`${data.reporting_device_count} reporting`}
        />
        <Stat
          label="Measured usage"
          value={formatBytes(data.total_bytes)}
          sub={`${formatBytes(data.total_received_bytes)} down · ${formatBytes(data.total_sent_bytes)} up`}
        />
        <Stat
          label="Stale"
          value={data.stale_device_count}
          tone={data.stale_device_count > 0 ? "warn" : "default"}
          sub={data.stale_device_count > 0 ? "Not reporting recently" : "All current"}
        />
        <Stat
          label="Revoked"
          value={data.revoked_device_count}
          sub="Credentials invalidated"
        />
      </div>

      {(data.measurement_warnings.length > 0 || data.stale_devices.length > 0) && (
        <Panel className="border-warn/30 bg-warn/5 p-4">
          <p className="text-sm font-medium text-warn">Collection health</p>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            {data.measurement_warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
            {data.stale_devices.slice(0, 4).map((d) => (
              <li key={d.id}>
                <Link to={`/devices/${d.id}`} className="underline decoration-dotted">
                  {d.name}
                </Link>{" "}
                last reported {relativeTime(d.last_seen_at)}.
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel>
        <PanelHeader
          title="Usage this period"
          action={
            <button
              onClick={() => setShowSeries((s) => !s)}
              className="text-xs text-muted hover:text-ink dark:hover:text-white"
            >
              {showSeries ? "Hide chart" : "Show chart"}
            </button>
          }
        />
        <div className="px-4 py-4 sm:px-5">
          <div className="mb-3">
            <ChartLegend />
          </div>
          {showSeries ? (
            <UsageChart series={data.usage_series} />
          ) : (
            <p className="py-10 text-center text-sm text-muted">Chart hidden.</p>
          )}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Groups" />
        {!anyGroups ? (
          <EmptyState
            title="No groups yet"
            body="Create a group to assign a monthly quota and start tracking usage."
            action={
              <Link
                to="/groups"
                className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white dark:bg-white dark:text-ink"
              >
                Go to groups
              </Link>
            }
          />
        ) : (
          <ul className="divide-y divide-line">
            {data.groups.map((g) => (
              <li key={g.group_id} className="px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/groups/${g.group_id}`}
                      className="font-display font-semibold hover:text-signal"
                    >
                      {g.group_name}
                    </Link>
                    <span className="text-xs text-muted">
                      {g.device_count} device{g.device_count === 1 ? "" : "s"}
                    </span>
                    <QualityTag quality={g.measurement_quality} />
                  </div>
                  <div className="tnum text-sm text-muted">
                    {formatBytes(g.remaining_bytes)} left
                  </div>
                </div>
                <div className="mt-3">
                  <QuotaMeter
                    used={g.used_bytes}
                    quota={g.quota_bytes}
                    percentage={g.percentage_used}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel>
        <PanelHeader title="Recent activity" />
        {data.recent_events.length === 0 ? (
          <EmptyState title="Quiet so far" body="Threshold and enrollment events will appear here." />
        ) : (
          <ul className="divide-y divide-line">
            {data.recent_events.map((e) => (
              <li key={e.id} className="flex items-start gap-3 px-4 py-3 text-sm sm:px-5">
                <span className="mt-1.5">
                  <SeverityDot severity={e.severity} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate">{e.message ?? e.event_type}</p>
                  <p className="tnum text-xs text-faint">
                    {e.event_type} · {relativeTime(e.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <p className="text-xs text-faint">
        Server state as of {formatDate(data.generated_at)} — refreshed every 30
        seconds.
      </p>
    </div>
  );
}