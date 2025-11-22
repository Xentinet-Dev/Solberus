"use client";

import { useQuery } from "@tanstack/react-query";
import { botApi, walletApi } from "@/lib/api";
import { useAppStore } from "@/store/app-store";

export default function QuickStats() {
  const wallet = useAppStore((state) => state.wallet);
  const bots = useAppStore((state) => state.bots);

  const { data: balance } = useQuery({
    queryKey: ["wallet-balance", wallet],
    queryFn: () => walletApi.balance(wallet || undefined),
    enabled: !!wallet,
    refetchInterval: 10000,
  });

  const activeBots = bots.filter((b) => b.status?.running).length;
  const totalTrades = bots.reduce(
    (sum, b) => sum + (b.status?.trade_history?.length || 0),
    0
  );
  const totalPnL = bots.reduce((sum, b) => {
    if (!b.status?.positions) return sum;
    return (
      sum +
      Object.values(b.status.positions).reduce(
        (pSum: number, pos: any) => pSum + (pos.pnl || 0),
        0
      )
    );
  }, 0);

  const stats = [
    {
      label: "Wallet Balance",
      value: balance?.balance
        ? `${balance.balance.toFixed(4)} SOL`
        : "0.0000 SOL",
      color: "text-accent-primary",
    },
    {
      label: "Active Bots",
      value: activeBots.toString(),
      color: "text-accent-success",
    },
    {
      label: "Total Trades",
      value: totalTrades.toString(),
      color: "text-accent-secondary",
    },
    {
      label: "Total P&L",
      value: `${totalPnL >= 0 ? "+" : ""}${totalPnL.toFixed(4)} SOL`,
      color: totalPnL >= 0 ? "text-accent-success" : "text-accent-danger",
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 px-6 py-4">
      {stats.map((s, i) => (
        <div
          key={i}
          className="bg-bg-tertiary border border-border rounded-lg p-4 hover:border-accent-primary/50 transition-colors"
        >
          <div className="text-text-secondary text-xs uppercase tracking-wide mb-1">
            {s.label}
          </div>
          <div className={`text-2xl font-bold font-mono ${s.color}`}>
            {s.value}
          </div>
        </div>
      ))}
    </div>
  );
}

