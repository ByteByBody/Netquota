import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { UsagePoint } from "../types";
import { formatBytes } from "../lib/format";

// Daily usage: download (received) stacked under upload (sent). A single chart
// characteristic of the domain rather than a generic dashboard bar.
export function UsageChart({
  series,
  height = 240,
}: {
  series: UsagePoint[];
  height?: number;
}) {
  const data = series.map((p) => ({
    day: p.bucket,
    received: p.received_bytes,
    sent: p.sent_bytes,
  }));
  const label = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

  if (data.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-muted">
        No usage recorded for this period yet.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="down" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2C6BD8" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#2C6BD8" stopOpacity={0.05} />
            </linearGradient>
            <linearGradient id="up" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#7A5AF8" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#7A5AF8" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="2 4" stroke="rgb(148 163 178 / 0.25)" vertical={false} />
          <XAxis
            dataKey="day"
            tickFormatter={label}
            tick={{ fontSize: 11, fill: "rgb(140 151 162)" }}
            axisLine={false}
            tickLine={false}
            minTickGap={24}
          />
          <YAxis
            tickFormatter={(v) => formatBytes(v, 0)}
            tick={{ fontSize: 11, fill: "rgb(140 151 162)" }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 8,
              border: "1px solid rgb(148 163 178 / 0.3)",
              background: "rgb(var(--surface))",
              fontSize: 12,
            }}
            labelFormatter={label}
            formatter={(value: number, name: string) => [
              formatBytes(value),
              name === "received" ? "Download" : "Upload",
            ]}
          />
          <Area
            type="monotone"
            dataKey="received"
            stackId="1"
            stroke="#2C6BD8"
            fill="url(#down)"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="sent"
            stackId="1"
            stroke="#7A5AF8"
            fill="url(#up)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ChartLegend() {
  return (
    <div className="flex items-center gap-4 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-3 rounded-sm bg-down" aria-hidden /> Download
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2 w-3 rounded-sm bg-up" aria-hidden /> Upload
      </span>
    </div>
  );
}