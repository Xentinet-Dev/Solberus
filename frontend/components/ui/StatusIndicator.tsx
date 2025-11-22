"use client";

export default function StatusIndicator() {
  return (
    <div className="flex items-center gap-2">
      <span className="w-3 h-3 rounded-full bg-accent-success animate-pulse shadow-success"></span>
      <span className="text-sm text-text-secondary">Connected</span>
    </div>
  );
}

