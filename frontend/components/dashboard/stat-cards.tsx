"use client";

export function StatCards() {
  // TODO: Get from React Query
  const stats = {
    walletBalance: 0.0049,
    activeBots: 0,
    totalTrades: 0,
    totalPnL: 0.0,
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      <StatCard
        label="Wallet Balance"
        value={`${stats.walletBalance.toFixed(4)} SOL`}
        color="text-accent-primary"
      />
      <StatCard
        label="Active Bots"
        value={stats.activeBots.toString()}
        color="text-accent-success"
      />
      <StatCard
        label="Total Trades"
        value={stats.totalTrades.toString()}
        color="text-text-primary"
      />
      <StatCard
        label="Total P&L"
        value={`${stats.totalPnL >= 0 ? "+" : ""}${stats.totalPnL.toFixed(4)} SOL`}
        color={stats.totalPnL >= 0 ? "text-accent-success" : "text-accent-danger"}
      />
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-bg-tertiary border border-border rounded-lg p-6 hover:border-accent-primary/50 transition-colors">
      <div className="text-xs uppercase tracking-wide text-text-muted mb-2">
        {label}
      </div>
      <div className={`text-2xl font-bold font-mono ${color}`}>
        {value}
      </div>
    </div>
  );
}

