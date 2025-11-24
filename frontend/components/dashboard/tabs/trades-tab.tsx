"use client";

import { useState, useEffect } from "react";
import {
  FileText,
  TrendingUp,
  TrendingDown,
  Clock,
  Target,
  CheckCircle,
  XCircle,
  Activity,
  AlertTriangle,
  Filter,
  Download,
  ExternalLink,
  DollarSign,
  Percent,
} from "lucide-react";

interface Trade {
  id: string;
  token_address: string;
  token_symbol: string;
  strategy: string;
  action: "buy" | "sell";
  entry_price: number;
  exit_price?: number;
  amount: number;
  pnl?: number;
  pnl_percent?: number;
  status: "active" | "completed" | "failed";
  entry_time: number;
  exit_time?: number;
  hold_time?: number;
  confidence: number;
  reason: string;
  exit_reason?: string;
}

export function TradesTab() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "active" | "completed" | "failed">("all");
  const [strategyFilter, setStrategyFilter] = useState<string>("all");

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 3000); // Poll every 3s
    return () => clearInterval(interval);
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await fetch("/api/trades/history");
      if (response.ok) {
        const data = await response.json();
        setTrades(data.trades || []);
      }
    } catch (error) {
      console.error("Failed to fetch trades:", error);
    } finally {
      setLoading(false);
    }
  };

  const exportTrades = async () => {
    try {
      const response = await fetch("/api/trades/export");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `solberus-trades-${Date.now()}.csv`;
      a.click();
    } catch (error) {
      console.error("Failed to export trades:", error);
    }
  };

  const filteredTrades = trades.filter((trade) => {
    if (filter !== "all" && trade.status !== filter) return false;
    if (strategyFilter !== "all" && trade.strategy !== strategyFilter) return false;
    return true;
  });

  const stats = {
    total: trades.length,
    active: trades.filter((t) => t.status === "active").length,
    completed: trades.filter((t) => t.status === "completed").length,
    failed: trades.filter((t) => t.status === "failed").length,
    total_pnl: trades
      .filter((t) => t.pnl !== undefined)
      .reduce((sum, t) => sum + (t.pnl || 0), 0),
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-secondary">
          <Activity className="w-5 h-5 animate-pulse" />
          <span className="font-mono">LOADING OPERATION LOGS...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border border-cyan-500/30 bg-gradient-to-r from-cyan-900/20 to-bg-tertiary rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-7 h-7 text-cyan-500" />
              <h1 className="text-2xl font-bold tracking-wide text-text-primary font-mono">
                OPERATION LOGS
              </h1>
            </div>
            <p className="text-sm text-text-secondary font-mono">
              TRADE EXECUTION HISTORY // REAL-TIME COMBAT REPORTS
            </p>
          </div>
          <button
            onClick={exportTrades}
            className="flex items-center gap-2 px-4 py-2 bg-cyan-900/30 border border-cyan-500/50 rounded-lg text-cyan-400 hover:bg-cyan-900/50 transition-all font-mono text-sm"
            title="Export all trade data. For your accountant, or the IRS."
          >
            <Download className="w-4 h-4" />
            EXPORT
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard
          label="TOTAL OPS"
          value={stats.total.toString()}
          icon={<FileText className="w-4 h-4" />}
          color="blue"
        />
        <StatCard
          label="ACTIVE"
          value={stats.active.toString()}
          icon={<Activity className="w-4 h-4" />}
          color="yellow"
        />
        <StatCard
          label="COMPLETED"
          value={stats.completed.toString()}
          icon={<CheckCircle className="w-4 h-4" />}
          color="green"
        />
        <StatCard
          label="FAILED"
          value={stats.failed.toString()}
          icon={<XCircle className="w-4 h-4" />}
          color="red"
        />
        <StatCard
          label="TOTAL P&L"
          value={`${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toFixed(2)} SOL`}
          icon={<DollarSign className="w-4 h-4" />}
          color={stats.total_pnl >= 0 ? "green" : "red"}
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-text-muted" />
          <span className="text-sm font-mono text-text-muted">STATUS:</span>
          {(["all", "active", "completed", "failed"] as const).map((status) => (
            <button
              key={status}
              onClick={() => setFilter(status)}
              className={`px-3 py-1 text-xs font-mono rounded border transition-all ${
                filter === status
                  ? "bg-blue-900/50 border-blue-500/50 text-blue-400"
                  : "bg-bg-tertiary border-border text-text-muted hover:border-blue-500/30"
              }`}
            >
              {status.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-mono text-text-muted">STRATEGY:</span>
          <select
            value={strategyFilter}
            onChange={(e) => setStrategyFilter(e.target.value)}
            className="px-3 py-1 text-xs font-mono bg-bg-tertiary border border-border rounded text-text-primary"
          >
            <option value="all">ALL</option>
            <option value="snipe">SNIPE</option>
            <option value="momentum">MOMENTUM</option>
            <option value="reversal">REVERSAL</option>
            <option value="whale_copy">WHALE COPY</option>
            <option value="social_signals">SOCIAL SIGNALS</option>
          </select>
        </div>
      </div>

      {/* Trades List */}
      <div className="space-y-3">
        {filteredTrades.length === 0 ? (
          <div className="border border-border rounded-lg p-8 text-center">
            <FileText className="w-12 h-12 text-text-muted mx-auto mb-3" />
            <p className="text-text-secondary font-mono">
              No operations recorded yet.
            </p>
            <p className="text-sm text-text-muted italic mt-1">
              Deploy the sentinel to start trading. Or watch paint dry.
            </p>
          </div>
        ) : (
          filteredTrades.map((trade) => (
            <TradeCard key={trade.id} trade={trade} />
          ))
        )}
      </div>

      {/* Warning */}
      {stats.active > 0 && (
        <div className="border border-yellow-500/30 bg-yellow-900/10 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
            <p className="text-sm text-text-secondary">
              <span className="font-mono text-yellow-500">{stats.active} active position(s).</span>
              {" "}
              <span className="text-text-muted italic">
                Exit liquidity might be you. Monitor closely.
              </span>
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color: "blue" | "green" | "red" | "yellow";
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  const colorClasses = {
    blue: "border-blue-500/30 bg-blue-900/10 text-blue-400",
    green: "border-green-500/30 bg-green-900/10 text-green-400",
    red: "border-red-500/30 bg-red-900/10 text-red-400",
    yellow: "border-yellow-500/30 bg-yellow-900/10 text-yellow-400",
  };

  return (
    <div className={`border ${colorClasses[color]} rounded-lg p-4`}>
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-xs font-mono text-text-muted uppercase">
          {label}
        </span>
      </div>
      <div className="text-xl font-bold font-mono">{value}</div>
    </div>
  );
}

interface TradeCardProps {
  trade: Trade;
}

function TradeCard({ trade }: TradeCardProps) {
  const isProfitable = trade.pnl !== undefined && trade.pnl > 0;
  const isActive = trade.status === "active";
  const isFailed = trade.status === "failed";

  const statusConfig = {
    active: {
      badge: "bg-yellow-900/30 border-yellow-500/50 text-yellow-400",
      label: "ACTIVE",
      icon: <Activity className="w-4 h-4 animate-pulse" />,
    },
    completed: {
      badge: isProfitable
        ? "bg-green-900/30 border-green-500/50 text-green-400"
        : "bg-red-900/30 border-red-500/50 text-red-400",
      label: isProfitable ? "WIN" : "LOSS",
      icon: isProfitable ? (
        <CheckCircle className="w-4 h-4" />
      ) : (
        <XCircle className="w-4 h-4" />
      ),
    },
    failed: {
      badge: "bg-red-900/30 border-red-500/50 text-red-400",
      label: "FAILED",
      icon: <AlertTriangle className="w-4 h-4" />,
    },
  };

  const config = statusConfig[trade.status];

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
  };

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div
      className="border border-border bg-bg-tertiary rounded-lg p-5 hover:border-border/60 transition-all"
      title={trade.reason}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-4">
          <div className={`${trade.status === "completed" && isProfitable ? "text-green-400" : trade.status === "failed" || (trade.status === "completed" && !isProfitable) ? "text-red-400" : "text-yellow-400"} mt-1`}>
            {config.icon}
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-lg font-bold font-mono text-text-primary">
                {trade.token_symbol || trade.token_address.slice(0, 8)}
              </h3>
              <span className={`px-2 py-0.5 text-xs font-mono border rounded ${config.badge}`}>
                {config.label}
              </span>
              <span className="px-2 py-0.5 text-xs font-mono border border-blue-500/30 bg-blue-900/10 text-blue-400 rounded">
                {trade.strategy.toUpperCase()}
              </span>
            </div>
            <a
              href={`https://solscan.io/token/${trade.token_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono text-text-muted hover:text-cyan-400 flex items-center gap-1"
            >
              {trade.token_address}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {trade.pnl !== undefined && (
          <div className="text-right">
            <div className={`text-2xl font-bold font-mono ${isProfitable ? "text-green-400" : "text-red-400"}`}>
              {isProfitable ? "+" : ""}{trade.pnl.toFixed(4)} SOL
            </div>
            <div className={`text-sm font-mono ${isProfitable ? "text-green-400/70" : "text-red-400/70"}`}>
              {isProfitable ? "+" : ""}{trade.pnl_percent?.toFixed(1)}%
            </div>
          </div>
        )}
      </div>

      {/* Trade Details Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <DetailItem
          label="ENTRY"
          value={`${trade.entry_price.toFixed(8)} SOL`}
          subvalue={formatTime(trade.entry_time)}
        />
        {trade.exit_price && (
          <DetailItem
            label="EXIT"
            value={`${trade.exit_price.toFixed(8)} SOL`}
            subvalue={trade.exit_time ? formatTime(trade.exit_time) : "-"}
          />
        )}
        <DetailItem
          label="AMOUNT"
          value={`${trade.amount.toFixed(2)} SOL`}
          subvalue={`${(trade.confidence * 100).toFixed(0)}% confidence`}
        />
        {trade.hold_time && (
          <DetailItem
            label="HOLD TIME"
            value={formatDuration(trade.hold_time)}
            subvalue={isActive ? "Still holding" : "Position closed"}
          />
        )}
      </div>

      {/* Reason */}
      <div className="border-t border-border/30 pt-3">
        <p className="text-xs text-text-secondary">
          <span className="font-mono text-text-muted">ENTRY: </span>
          {trade.reason}
        </p>
        {trade.exit_reason && (
          <p className="text-xs text-text-secondary mt-1">
            <span className="font-mono text-text-muted">EXIT: </span>
            {trade.exit_reason}
          </p>
        )}
      </div>

      {/* Sarcastic Commentary */}
      {trade.status === "completed" && !isProfitable && (
        <div className="mt-3 pt-3 border-t border-border/30">
          <p className="text-xs text-red-400/70 italic">
            {trade.pnl && trade.pnl < -5
              ? "Ouch. That's gonna leave a mark."
              : "Could've been worse. Could've been a rug pull."}
          </p>
        </div>
      )}
      {trade.status === "completed" && isProfitable && trade.pnl && trade.pnl > 10 && (
        <div className="mt-3 pt-3 border-t border-border/30">
          <p className="text-xs text-green-400/70 italic">
            Nice exit. Sell before the whales do.
          </p>
        </div>
      )}
      {trade.status === "failed" && (
        <div className="mt-3 pt-3 border-t border-border/30">
          <p className="text-xs text-red-400/70 italic">
            Trade failed to execute. Network congestion, or the token rugged mid-transaction.
          </p>
        </div>
      )}
    </div>
  );
}

interface DetailItemProps {
  label: string;
  value: string;
  subvalue?: string;
}

function DetailItem({ label, value, subvalue }: DetailItemProps) {
  return (
    <div>
      <div className="text-xs font-mono text-text-muted uppercase mb-1">
        {label}
      </div>
      <div className="text-sm font-bold font-mono text-text-primary">
        {value}
      </div>
      {subvalue && (
        <div className="text-xs text-text-muted mt-0.5">
          {subvalue}
        </div>
      )}
    </div>
  );
}
