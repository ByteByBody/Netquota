import { useState } from "react";
import { useApi, useAsyncAction } from "../hooks/useApi";
import { api } from "../api/client";
import type { EnrollmentCodeCreated, Group } from "../types";
import {
  Button,
  ErrorBox,
  Field,
  Loading,
  PageHeader,
  Panel,
  PanelHeader,
  inputClass,
} from "../components/layout";
import { formatDate } from "../lib/format";

export function SettingsPage() {
  const groups = useApi<Group[]>(() => api.groups());
  const [label, setLabel] = useState("");
  const [groupId, setGroupId] = useState("");
  const [created, setCreated] = useState<EnrollmentCodeCreated | null>(null);
  const [ttl, setTtl] = useState(30);
  const { busy, error, run } = useAsyncAction();

  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  if (groups.loading && !groups.data) return <Loading label="Loading settings…" />;
  if (groups.error && !groups.data)
    return <ErrorBox message={groups.error} onRetry={groups.refresh} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Enrollment, reporting, and deployment information for this server."
      />

      <Panel>
        <PanelHeader title="Enrollment codes" />
        <div className="grid gap-4 px-4 py-4 sm:grid-cols-3 sm:px-5">
          <Field label="Label" hint="Who or what this code is for.">
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Living room PC"
              className={inputClass}
            />
          </Field>
          <Field label="Assign to group">
            <select
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
              className={inputClass}
            >
              <option value="">Unassigned</option>
              {(groups.data ?? []).map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Expires in (minutes)">
            <input
              type="number"
              min={1}
              max={1440}
              value={ttl}
              onChange={(e) => setTtl(Number(e.target.value))}
              className={inputClass}
            />
          </Field>
        </div>
        <div className="flex justify-end border-t border-line px-4 py-3 sm:px-5">
          <Button
            disabled={busy}
            onClick={() =>
              run(async () => {
                const code = await api.createEnrollmentCode({
                  label: label || null,
                  ttl_minutes: ttl,
                  group_id: groupId || null,
                });
                setCreated(code);
                setLabel("");
              })
            }
          >
            Generate code
          </Button>
        </div>
        {error && <p className="px-4 pb-3 text-sm text-danger sm:px-5">{error}</p>}
        {created && (
          <div className="border-t border-line bg-signal/5 px-4 py-4 sm:px-5">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">
              Single-use code — shown once, expires {formatDate(created.expires_at)}
            </p>
            <code className="mt-2 block break-all rounded-md border border-line bg-paper px-3 py-2 font-mono text-sm dark:bg-[#0F1519]">
              {created.code}
            </code>
            <p className="mt-2 text-xs text-muted">
              On the device, run:
              <br />
              <code className="font-mono">
                netquota-agent enroll --server {window.location.origin} --code {created.code} --name "My PC"
              </code>
            </p>
          </div>
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Agent reporting" />
          <dl className="space-y-3 px-4 py-4 text-sm sm:px-5">
            <Row label="Default interval">300 seconds</Row>
            <Row label="Heartbeat">300 seconds</Row>
            <Row label="Stale after">30 minutes without a report</Row>
            <Row label="Interface policy">Primary (excludes virtual/bridge/VPN)</Row>
            <Row label="Quota alerts">80%, 90%, 100% of the group quota</Row>
          </dl>
          <p className="border-t border-line px-4 py-3 text-xs text-muted sm:px-5">
            Change these on the server with the <code className="font-mono">NETQUOTA_*</code>{" "}
            environment variables (see docs/architecture.md).
          </p>
        </Panel>

        <Panel>
          <PanelHeader title="Server & deployment" />
          <dl className="space-y-3 px-4 py-4 text-sm sm:px-5">
            <Row label="API endpoint">
              <code className="font-mono text-xs">{window.location.origin}/api/v1</code>
            </Row>
            <Row label="Browser time zone">{tz}</Row>
            <Row label="API docs">/docs (on the server host)</Row>
            <Row label="Database">PostgreSQL via Docker Compose</Row>
          </dl>
          <p className="border-t border-line px-4 py-3 text-xs text-muted sm:px-5">
            Back up the database regularly; usage history is stored there. See
            docs/architecture.md for backup and restore commands.
          </p>
        </Panel>
      </div>

      <Panel className="border-up/30 bg-up/5 p-4">
        <p className="text-sm font-medium text-up">Demo data</p>
        <p className="mt-1 text-sm text-muted">
          Devices that report synthetic data are always labelled with the
          <span className="mx-1 rounded bg-up/10 px-1.5 font-medium text-up">Simulated</span>
          platform tag and a name prefix. Real measurements are never mixed with
          demo data. To remove demo data, revoke and delete the simulated device.
        </p>
      </Panel>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right">{children}</dd>
    </div>
  );
}