import { useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import { api } from "../api/client";
import type { Group } from "../types";
import {
  Button,
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  PageHeader,
  Panel,
  PanelHeader,
  inputClass,
} from "../components/layout";
import { QuotaMeter } from "../components/ui";
import { parseGib } from "../lib/format";

export function GroupsPage() {
  const groups = useApi<Group[]>(() => api.groups());
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [quota, setQuota] = useState("10");
  const [resetDay, setResetDay] = useState(1);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    try {
      await api.createGroup({
        name,
        quota_bytes: parseGib(quota),
        reset_day: resetDay,
      });
      setName("");
      setCreating(false);
      await groups.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    }
  }

  if (groups.loading && !groups.data) return <Loading label="Loading groups…" />;
  if (groups.error && !groups.data)
    return <ErrorBox message={groups.error} onRetry={groups.refresh} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Groups"
        description="A group pools the usage of its devices and holds a monthly quota."
        actions={
          <Button onClick={() => setCreating((c) => !c)}>
            {creating ? "Cancel" : "New group"}
          </Button>
        }
      />

      {creating && (
        <Panel className="animate-rise">
          <PanelHeader title="New group" />
          <div className="grid gap-4 px-4 py-4 sm:grid-cols-3 sm:px-5">
            <Field label="Name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className={inputClass}
                placeholder="Household"
              />
            </Field>
            <Field label="Monthly quota" hint="Binary units (GiB). Try “10” or “500 MiB”.">
              <input
                value={quota}
                onChange={(e) => setQuota(e.target.value)}
                className={inputClass}
              />
            </Field>
            <Field label="Reset day" hint="Day of month the quota period restarts.">
              <input
                type="number"
                min={1}
                max={28}
                value={resetDay}
                onChange={(e) => setResetDay(Number(e.target.value))}
                className={inputClass}
              />
            </Field>
          </div>
          {error && <p className="px-4 pb-3 text-sm text-danger sm:px-5">{error}</p>}
          <div className="flex justify-end border-t border-line px-4 py-3 sm:px-5">
            <Button onClick={create} disabled={!name.trim()}>
              Create group
            </Button>
          </div>
        </Panel>
      )}

      <GroupList groups={groups.data ?? []} onChanged={groups.refresh} />
    </div>
  );
}

function GroupList({
  groups,
  onChanged,
}: {
  groups: Group[];
  onChanged: () => void;
}) {
  if (groups.length === 0) {
    return (
      <Panel>
        <EmptyState
          title="No groups yet"
          body="Create your first group, set a monthly quota, then assign devices to it."
        />
      </Panel>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {groups.map((g) => (
        <GroupCard key={g.id} group={g} onChanged={onChanged} />
      ))}
    </div>
  );
}

function GroupCard({ group, onChanged }: { group: Group; onChanged: () => void }) {
  const usage = useApi(() => api.groupUsage(group.id), [group.id]);
  const summary = usage.data?.summary;

  return (
    <Panel as="article" className="animate-rise">
      <div className="flex items-start justify-between border-b border-line px-4 py-3 sm:px-5">
        <div>
          <Link
            to={`/groups/${group.id}`}
            className="font-display font-semibold hover:text-signal"
          >
            {group.name}
          </Link>
          <p className="text-xs text-muted">
            {group.device_count} device{group.device_count === 1 ? "" : "s"} · resets
            day {group.reset_day}
          </p>
        </div>
        <button
          onClick={async () => {
            if (!confirm(`Delete group ${group.name}? Devices become unassigned.`))
              return;
            await api.deleteGroup(group.id);
            onChanged();
          }}
          className="text-xs text-muted hover:text-danger"
        >
          Delete
        </button>
      </div>
      <div className="px-4 py-4 sm:px-5">
        {summary ? (
          <QuotaMeter
            used={summary.used_bytes}
            quota={summary.quota_bytes}
            percentage={summary.percentage_used}
          />
        ) : (
          <p className="text-sm text-muted">Calculating…</p>
        )}
      </div>
    </Panel>
  );
}