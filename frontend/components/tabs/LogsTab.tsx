"use client";

export default function LogsTab() {
  return (
    <div className="bg-bg-tertiary border border-border rounded-lg p-4 h-full overflow-y-scroll font-mono text-sm">
      <div className="text-accent-primary">[12:34:23] Connected to RPC</div>
      <div className="text-accent-warning">[12:34:26] Sniper initialized</div>
      <div className="text-accent-success">[12:34:30] Buy executed: 0.27 SOL</div>
      <div className="text-accent-danger">[12:34:32] Risk alert: High slippage detected</div>
    </div>
  );
}

