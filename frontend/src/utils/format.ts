const inrFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const intFormatter = new Intl.NumberFormat("en-IN");

const istDateFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
});

export function formatINR(value: number): string {
  return inrFormatter.format(value);
}

export function formatINRCompact(value: number): string {
  if (value >= 1e7) {
    return `₹${(value / 1e7).toFixed(2)} Cr`;
  }
  if (value >= 1e5) {
    return `₹${(value / 1e5).toFixed(2)} L`;
  }
  return inrFormatter.format(value);
}

export function formatInteger(value: number): string {
  return intFormatter.format(value);
}

export function formatTimestampIST(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) return "—";
  return `${istDateFormatter.format(parsed)} IST`;
}

export function formatDuration(
  startedAt: string | null | undefined,
  completedAt: string | null | undefined
): string {
  if (!startedAt || !completedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "—";

  const totalSec = Math.round((end - start) / 1000);
  if (totalSec < 60) return `${totalSec}s`;
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  return `${mins}m ${secs}s`;
}
