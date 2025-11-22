"use client";

import { useAppStore } from "@/store/app-store";

export default function TradesTab() {
  const bots = useAppStore((state) => state.bots);

  // Collect all trades from all bots
  const allTrades = bots.flatMap((bot) => {
    if (!bot.status?.trade_history) return [];
    return bot.status.trade_history.map((trade: any) => ({
      ...trade,
      botId: bot.bot_id,
    }));
  });

  // Sort by time (newest first)
  allTrades.sort((a, b) => {
    const timeA = a.timestamp || a.time || 0;
    const timeB = b.timestamp || b.time || 0;
    return timeB - timeA;
  });

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">Trade History</h2>
        <p className="text-text-secondary text-sm">
          Complete history of all trades across all bots.
        </p>
      </div>

      <div className="bg-bg-tertiary border border-border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-bg-secondary">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Time
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Symbol
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Price
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Amount
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  TX Hash
                </th>
                <th className="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-text-secondary">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {allTrades.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-text-muted">
                    No trades yet
                  </td>
                </tr>
              ) : (
                allTrades.slice(0, 100).map((trade, index) => {
                  const tradeTime = trade.timestamp || trade.time;
                  const timeStr = tradeTime
                    ? new Date(
                        typeof tradeTime === "number" ? tradeTime * 1000 : tradeTime
                      ).toLocaleString()
                    : "N/A";
                  const action = trade.action || trade.type || "N/A";
                  const status = trade.status || "pending";
                  const isBuy = action.toLowerCase() === "buy";
                  const isSuccess = status === "success" || status === "completed";

                  return (
                    <tr key={index} className="hover:bg-bg-hover transition-colors">
                      <td className="px-6 py-4 text-sm">{timeStr}</td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-2 py-1 text-xs rounded font-semibold ${
                            isBuy
                              ? "bg-accent-success/20 text-accent-success"
                              : "bg-accent-danger/20 text-accent-danger"
                          }`}
                        >
                          {action.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-medium">
                        {trade.symbol || trade.token_symbol || "N/A"}
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {trade.price?.toFixed(8) || "0.00000000"}
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {trade.amount?.toFixed(4) || "0.0000"} {trade.currency || "SOL"}
                      </td>
                      <td className="px-6 py-4">
                        {trade.tx_hash ? (
                          <a
                            href={`https://solscan.io/tx/${trade.tx_hash}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-accent-primary hover:underline font-mono text-sm"
                          >
                            {trade.tx_hash.slice(0, 8)}...
                          </a>
                        ) : (
                          <span className="text-text-muted">N/A</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-2 py-1 text-xs rounded ${
                            isSuccess
                              ? "bg-accent-success/20 text-accent-success"
                              : status === "failed" || status === "error"
                              ? "bg-accent-danger/20 text-accent-danger"
                              : "bg-accent-warning/20 text-accent-warning"
                          }`}
                        >
                          {status.toUpperCase()}
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

