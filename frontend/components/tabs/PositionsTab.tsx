"use client";

import { useAppStore } from "@/store/app-store";

export default function PositionsTab() {
  const bots = useAppStore((state) => state.bots);

  // Collect all positions from all bots
  const allPositions = bots.flatMap((bot) => {
    if (!bot.status?.positions) return [];
    return Object.entries(bot.status.positions).map(([mint, pos]: [string, any]) => ({
      ...pos,
      mint,
      botId: bot.bot_id,
    }));
  });

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">Open Positions</h2>
        <p className="text-text-secondary text-sm">
          View all open trading positions across all active bots.
        </p>
      </div>

      <div className="bg-bg-tertiary border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-bg-secondary">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Symbol
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Entry Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Quantity
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Current Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  P&L
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  P&L %
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {allPositions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-text-muted">
                    No open positions
                  </td>
                </tr>
              ) : (
                allPositions.map((pos, index) => {
                  const pnl = pos.pnl || 0;
                  const pnlPercent = pos.pnl_percent || 0;
                  const isProfit = pnl >= 0;

                  return (
                    <tr key={index} className="hover:bg-bg-hover transition-colors">
                      <td className="px-6 py-4 font-medium">{pos.symbol || pos.mint.slice(0, 8)}</td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {pos.entry_price?.toFixed(8) || "0.00000000"}
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {pos.quantity?.toFixed(4) || "0.0000"}
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {pos.current_price?.toFixed(8) || "0.00000000"}
                      </td>
                      <td
                        className={`px-6 py-4 font-mono text-sm font-semibold ${
                          isProfit ? "text-accent-success" : "text-accent-danger"
                        }`}
                      >
                        {isProfit ? "+" : ""}
                        {pnl.toFixed(4)} SOL
                      </td>
                      <td
                        className={`px-6 py-4 font-mono text-sm font-semibold ${
                          isProfit ? "text-accent-success" : "text-accent-danger"
                        }`}
                      >
                        {isProfit ? "+" : ""}
                        {(pnlPercent * 100).toFixed(2)}%
                      </td>
                      <td className="px-6 py-4">
                        <span className="px-2 py-1 text-xs rounded bg-accent-success/20 text-accent-success">
                          Active
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

