import type { ReactNode } from "react";
import { formatBytes, formatPercent } from "../lib/format";

// The quota meter is the dashboard's signature element: a horizontal bar with
// physical tick marks at 80/90/100% that stay visible whether they are crossed
// or not, so the shape of the quota is legible at a glance.
export function QuotaMeter({
  used,
  quota,
  percentage,
  compact = false,
}: {
  used: number;
  quota: number;
  percentage: number;
  compact?: boolean;
}) {
  const pct = quota > 0 ? Math.min(100, (used / quota) * 100) : 0;
  const color =
    percentage >= 100
      ? "bg-danger"
      : percentage >= 90
        ? "bg-warn"
        : percentage >= 80
          ? "bg-signal"
          : "bg-signal";
  const over = percentage >= 100;

  return (
    <div className="w-full">
      <div
        className="relative h-3 w-full overflow-hidden rounded-full bg-line/60"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={quota}
        aria-valuenow={used}
        aria-label={`Quota used: ${formatPercent(percentage)}`}
      >
        <div
          className={`h-full rounded-full ${color} transition-[width] duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
        {/* Threshold ticks at 80/90/100% */}
        {[80, 90, 100].map((t) => (
          <span
            key={t}
            className="absolute top-0 h-full w-px bg-ink/25 dark:bg-white/30"
            style={{ left: `${t}%` }}
            aria-hidden
          />
        ))}
        {over && (
          <span
            className="absolute right-1 top-1/2 -translate-y-1/2 text-[11px] font-semibold text-white"
            aria-hidden
          >
            over
          </span>
        )}
      </div>
      {!compact && (
        <div className="mt-2 flex items-baseline justify-between text-sm">
          <span className="tnum text-muted">
            <span className="text-ink dark:text-white">{formatBytes(used)}</span> of{" "}
            {formatBytes(quota)}
          </span>
          <span className="tnum font-medium">{formatPercent(percentage)}</span>
        </div>
      )}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  tone?: "default" | "signal" | "warn" | "danger";
}) {
  const toneClass = {
    default: "text-ink dark:text-white",
    signal: "text-signal",
    warn: "text-warn",
    danger: "text-danger",
  }[tone];
  return (
    <div className="animate-rise">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">
        {label}
      </div>
      <div className={`tnum mt-1 font-display text-3xl font-semibold ${toneClass}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-sm text-muted">{sub}</div>}
    </div>
  );
}

export function SeverityDot({ severity }: { severity: string }) {
  const color =
    severity === "critical"
      ? "bg-danger"
      : severity === "warning"
        ? "bg-warn"
        : "bg-signal";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} aria-hidden />;
}

export function PlatformTag({ platform }: { platform: string }) {
  const map: Record<string, string> = {
    windows: "Windows",
    linux: "Linux",
    android: "Android",
    ios: "iOS",
    simulator: "Simulated",
    unknown: "Unknown",
  };
  const simulated = platform === "simulator";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium ${
        simulated
          ? "bg-up/10 text-up"
          : "bg-line/60 text-muted dark:text-[#c6cfd8]"
      }`}
    >
      {map[platform] ?? platform}
      {simulated && <span title="Synthetic data">•</span>}
    </span>
  );
}

export function QualityTag({
  quality,
  scope,
}: {
  quality: string;
  scope?: string;
}) {
  if (quality === "exact" || !quality || quality === "unknown") return null;
  const label =
    scope === "app_only"
      ? "App-only measurement"
      : scope === "partial"
        ? "Partial coverage"
        : quality === "estimated"
          ? "Estimated"
          : "Partial";
  return (
    <span className="inline-flex items-center gap-1 rounded bg-warn/10 px-1.5 py-0.5 text-xs font-medium text-warn">
      {label}
    </span>
  );
}