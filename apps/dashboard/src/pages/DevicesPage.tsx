import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import type { Device, Group } from "../types";
import {
  EmptyState,
  ErrorBox,
  Loading,
  PageHeader,
  Panel,
  inputClass,
} from "../components/layout";
import { PlatformTag, QualityTag } from "../components/ui";
import { relativeTime } from "../lib/format";

export function DevicesPage() {
  const devices = useApi<Device[]>(() => api.devices(), [], { pollMs: 30000 });
  const groups = useApi<Group[]>(() => api.groups());
  const [query, setQuery] = useState("");
  const [groupFilter, setGroupFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (devices.data ?? []).filter((d) => {
      if (groupFilter !== "all") {
        const gid = d.group_id ?? "none";
        if (groupFilter === "none" ? gid !== "none" : gid !== groupFilter)
          return false;
      }
      if (!q) return true;
      return (
        d.name.toLowerCase().includes(q) ||
        d.platform.toLowerCase().includes(q) ||
        (d.group_name ?? "").toLowerCase().includes(q)
      );
    });
  }, [devices.data, query, groupFilter]);

  if (devices.loading && !devices.data)
    return <Loading label="Listing devices…" />;
  if (devices.error && !devices.data)
    return <ErrorBox message={devices.error} onRetry={devices.refresh} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Devices"
        description="Every device that has enrolled with this server. Revoking a device invalidates its credential."
      />

      <div className="flex flex-wrap gap-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, platform, or group"
          className={`${inputClass} max-w-xs`}
          aria-label="Search devices"
        />
        <select
          value={groupFilter}
          onChange={(e) => setGroupFilter(e.target.value)}
          className={`${inputClass} max-w-xs`}
          aria-label="Filter by group"
        >
          <option value="all">All groups</option>
          <option value="none">Unassigned</option>
          {(groups.data ?? []).map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>
      </div>

      <Panel>
        {filtered.length === 0 ? (
          <EmptyState
            title="No devices match"
            body={
              devices.data && devices.data.length > 0
                ? "Try clearing the search or filter."
                : "Enroll a device from Settings with a single-use enrollment code."
            }
            action={
              <Link
                to="/settings"
                className="rounded-md bg-ink px-3 py-1.5 text-sm font-medium text-white dark:bg-white dark:text-ink"
              >
                Generate an enrollment code
              </Link>
            }
          />
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-4 py-3 font-medium sm:px-5">Device</th>
                    <th className="px-3 py-3 font-medium">Platform</th>
                    <th className="px-3 py-3 font-medium">Group</th>
                    <th className="px-3 py-3 font-medium">Status</th>
                    <th className="px-3 py-3 font-medium">Quality</th>
                    <th className="px-3 py-3 font-medium">Last report</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {filtered.map((d) => (
                    <tr key={d.id} className="hover:bg-line/20">
                      <td className="px-4 py-3 sm:px-5">
                        <Link
                          to={`/devices/${d.id}`}
                          className="font-medium hover:text-signal"
                        >
                          {d.name}
                        </Link>
                        <div className="text-xs text-faint">
                          {d.agent_version ? `agent ${d.agent_version}` : "—"}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <PlatformTag platform={d.platform} />
                      </td>
                      <td className="px-3 py-3 text-muted">
                        {d.group_name ?? "Unassigned"}
                      </td>
                      <td className="px-3 py-3">
                        <StatusPill device={d} />
                      </td>
                      <td className="px-3 py-3">
                        <QualityTag
                          quality={d.measurement_quality}
                          scope={d.measurement_scope}
                        />
                        {d.measurement_quality === "exact" && (
                          <span className="text-xs text-faint">Full</span>
                        )}
                      </td>
                      <td className="tnum px-3 py-3 text-muted">
                        {relativeTime(d.last_seen_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <ul className="divide-y divide-line md:hidden">
              {filtered.map((d) => (
                <li key={d.id} className="px-4 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <Link
                      to={`/devices/${d.id}`}
                      className="font-medium hover:text-signal"
                    >
                      {d.name}
                    </Link>
                    <StatusPill device={d} />
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
                    <PlatformTag platform={d.platform} />
                    <span>{d.group_name ?? "Unassigned"}</span>
                    <QualityTag
                      quality={d.measurement_quality}
                      scope={d.measurement_scope}
                    />
                    <span className="tnum">{relativeTime(d.last_seen_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Panel>
    </div>
  );
}

export function StatusPill({ device }: { device: Device }) {
  if (!device.is_active)
    return (
      <span className="rounded-full bg-danger/10 px-2 py-0.5 text-xs font-medium text-danger">
        Revoked
      </span>
    );
  if (device.is_stale)
    return (
      <span className="rounded-full bg-warn/10 px-2 py-0.5 text-xs font-medium text-warn">
        Stale
      </span>
    );
  return (
    <span className="rounded-full bg-signal/10 px-2 py-0.5 text-xs font-medium text-signal">
      Reporting
    </span>
  );
}