// Byte formatting. Bytes are stored as integers; we only convert for display
// and always label the unit. NetQuota uses binary units (GiB) by default.
const UNITS = ["B", "KiB", "MiB", "GiB", "TiB", "PiB"];

export function formatBytes(bytes: number, decimals = 1): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    UNITS.length - 1,
  );
  const value = bytes / Math.pow(1024, i);
  const d = i === 0 ? 0 : decimals;
  return `${value.toFixed(d)} ${UNITS[i]}`;
}

export function parseGib(text: string): number {
  // Accepts "10", "10 GiB", "10 GB" and returns bytes (GiB interpretation).
  const match = text.trim().match(/^([\d.]+)\s*(gib|gb|g|mib|mb|m)?$/i);
  if (!match) return 0;
  const value = parseFloat(match[1]);
  const unit = (match[2] || "gib").toLowerCase();
  const factor: Record<string, number> = {
    b: 1,
    mib: 1024 ** 2,
    mb: 1024 ** 2,
    m: 1024 ** 2,
    gib: 1024 ** 3,
    gb: 1024 ** 3,
    g: 1024 ** 3,
  };
  return Math.round(value * (factor[unit] ?? 1024 ** 3));
}

export function formatPercent(value: number): string {
  return `${value.toFixed(value >= 10 ? 0 : 1)}%`;
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "never";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}