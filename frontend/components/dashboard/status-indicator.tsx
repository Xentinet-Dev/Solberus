"use client";

export function StatusIndicator() {
  return (
    <div className="flex items-center gap-2 px-4 py-2 bg-bg-tertiary rounded-lg border border-border">
      <div className="w-2.5 h-2.5 rounded-full bg-accent-success animate-pulse-glow" />
      <span className="text-sm font-semibold text-text-primary">CONNECTED</span>
    </div>
  );
}

