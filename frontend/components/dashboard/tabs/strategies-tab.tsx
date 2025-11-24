"use client";

import { useState, useEffect } from "react";
import {
  Target,
  TrendingUp,
  TrendingDown,
  Users,
  Radio,
  Settings,
  Power,
  CheckCircle,
  XCircle,
  Activity,
  DollarSign,
  Percent,
  Clock,
  AlertTriangle
} from "lucide-react";

interface StrategyStats {
  name: string;
  enabled: boolean;
  trades_count: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_hold_time: number;
  confidence_avg: number;
  last_trade_time?: number;
}

interface StrategiesData {
  snipe: StrategyStats;
  momentum: StrategyStats;
  reversal: StrategyStats;
  whale_copy: StrategyStats;
  social_signals: StrategyStats;
  overall: {
    total_trades: number;
    total_wins: number;
    total_pnl: number;
    avg_win_rate: number;
    active_strategies: number;
  };
}

export function StrategiesTab() {
  const [strategies, setStrategies] = useState<StrategiesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  useEffect(() => {
    fetchStrategies();
    const interval = setInterval(fetchStrategies, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const fetchStrategies = async () => {
    try {
      const response = await fetch("/api/strategies/status");
      if (response.ok) {
        const data = await response.json();
        setStrategies(data);
      }
    } catch (error) {
      console.error("Failed to fetch strategies:", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleStrategy = async (strategyName: string, currentState: boolean) => {
    setToggling(strategyName);
    try {
      const response = await fetch("/api/strategies/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy: strategyName,
          enabled: !currentState,
        }),
      });

      if (response.ok) {
        await fetchStrategies();
      }
    } catch (error) {
      console.error("Failed to toggle strategy:", error);
    } finally {
      setToggling(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-secondary">
          <Activity className="w-5 h-5 animate-pulse" />
          <span className="font-mono">LOADING DEFENSE SYSTEMS...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border border-blue-500/30 bg-gradient-to-r from-blue-900/20 to-bg-tertiary rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <Target className="w-7 h-7 text-blue-500" />
          <h1 className="text-2xl font-bold tracking-wide text-text-primary font-mono">
            DEFENSE SYSTEMS OVERVIEW
          </h1>
        </div>
        <p className="text-sm text-text-secondary font-mono">
          AUTONOMOUS TRADING MODULES // 5 ACTIVE SYSTEMS // ADAPTIVE EXECUTION
        </p>
      </div>

      {/* Overall Stats */}
      {strategies?.overall && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="TOTAL OPERATIONS"
            value={strategies.overall.total_trades.toString()}
            icon={<Activity className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            label="SUCCESSFUL OPS"
            value={strategies.overall.total_wins.toString()}
            icon={<CheckCircle className="w-5 h-5" />}
            color="green"
          />
          <StatCard
            label="NET P&L"
            value={`${strategies.overall.total_pnl >= 0 ? '+' : ''}${strategies.overall.total_pnl.toFixed(2)} SOL`}
            icon={<DollarSign className="w-5 h-5" />}
            color={strategies.overall.total_pnl >= 0 ? "green" : "red"}
          />
          <StatCard
            label="AVG WIN RATE"
            value={`${(strategies.overall.avg_win_rate * 100).toFixed(0)}%`}
            icon={<Percent className="w-5 h-5" />}
            color="blue"
          />
        </div>
      )}

      {/* Strategy Cards */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-text-primary font-mono tracking-wide">
          ACTIVE DEFENSE MODULES
        </h2>

        {strategies && (
          <>
            <StrategyCard
              name="SNIPE MODULE"
              description="Fast-entry on new token launches"
              icon={<Target className="w-6 h-6" />}
              color="yellow"
              stats={strategies.snipe}
              onToggle={() => toggleStrategy("snipe", strategies.snipe.enabled)}
              isToggling={toggling === "snipe"}
              tooltip="Enters new launches within 5 minutes. High risk, high reward. Expect rugs."
            />

            <StrategyCard
              name="MOMENTUM TRACKER"
              description="RSI/MACD technical analysis"
              icon={<TrendingUp className="w-6 h-6" />}
              color="green"
              stats={strategies.momentum}
              onToggle={() => toggleStrategy("momentum", strategies.momentum.enabled)}
              isToggling={toggling === "momentum"}
              tooltip="Follow the trend until it doesn't. Technical indicators for the illusion of control."
            />

            <StrategyCard
              name="REVERSAL DETECTOR"
              description="Mean reversion on dips/peaks"
              icon={<TrendingDown className="w-6 h-6" />}
              color="purple"
              stats={strategies.reversal}
              onToggle={() => toggleStrategy("reversal", strategies.reversal.enabled)}
              isToggling={toggling === "reversal"}
              tooltip="Buy the dip, sell the peak. Works until the dip keeps dipping to zero."
            />

            <StrategyCard
              name="WHALE SHADOW"
              description="Copy successful whale trades"
              icon={<Users className="w-6 h-6" />}
              color="blue"
              stats={strategies.whale_copy}
              onToggle={() => toggleStrategy("whale_copy", strategies.whale_copy.enabled)}
              isToggling={toggling === "whale_copy"}
              tooltip="Follow the whales. They might know something, or they're exit liquidity farming."
            />

            <StrategyCard
              name="SOCIAL RADAR"
              description="Social media momentum signals"
              icon={<Radio className="w-6 h-6" />}
              color="pink"
              stats={strategies.social_signals}
              onToggle={() => toggleStrategy("social_signals", strategies.social_signals.enabled)}
              isToggling={toggling === "social_signals"}
              tooltip="Trade the hype. Most of it is bots and paid shillers, but sometimes it pumps."
            />
          </>
        )}
      </div>

      {/* Warning Banner */}
      <div className="border border-yellow-500/30 bg-yellow-900/10 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-500 mt-0.5" />
          <div>
            <p className="text-sm text-text-secondary leading-relaxed">
              All strategies operate autonomously based on configured parameters.
              {" "}
              <span className="text-yellow-500 font-mono">
                High risk, high volatility, high chance of getting rekt.
              </span>
              {" "}
              <span className="text-text-muted italic">
                Disable modules that hemorrhage capital.
              </span>
            </p>
          </div>
        </div>
      </div>
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
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs font-mono text-text-muted uppercase">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold font-mono">
        {value}
      </div>
    </div>
  );
}

interface StrategyCardProps {
  name: string;
  description: string;
  icon: React.ReactNode;
  color: "yellow" | "green" | "purple" | "blue" | "pink";
  stats: StrategyStats;
  onToggle: () => void;
  isToggling: boolean;
  tooltip: string;
}

function StrategyCard({
  name,
  description,
  icon,
  color,
  stats,
  onToggle,
  isToggling,
  tooltip,
}: StrategyCardProps) {
  const colorClasses = {
    yellow: {
      border: "border-yellow-500/30",
      bg: "bg-yellow-900/10",
      text: "text-yellow-400",
      badge: "bg-yellow-900/30 border-yellow-500/50",
    },
    green: {
      border: "border-green-500/30",
      bg: "bg-green-900/10",
      text: "text-green-400",
      badge: "bg-green-900/30 border-green-500/50",
    },
    purple: {
      border: "border-purple-500/30",
      bg: "bg-purple-900/10",
      text: "text-purple-400",
      badge: "bg-purple-900/30 border-purple-500/50",
    },
    blue: {
      border: "border-blue-500/30",
      bg: "bg-blue-900/10",
      text: "text-blue-400",
      badge: "bg-blue-900/30 border-blue-500/50",
    },
    pink: {
      border: "border-pink-500/30",
      bg: "bg-pink-900/10",
      text: "text-pink-400",
      badge: "bg-pink-900/30 border-pink-500/50",
    },
  };

  const colors = colorClasses[color];

  return (
    <div
      className={`border ${colors.border} ${colors.bg} rounded-lg p-6 transition-all hover:border-opacity-60`}
      title={tooltip}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-4">
          <div className={`${colors.text} mt-1`}>
            {icon}
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h3 className={`text-lg font-bold font-mono ${colors.text}`}>
                {name}
              </h3>
              <span
                className={`px-2 py-0.5 text-xs font-mono border rounded ${
                  stats.enabled
                    ? "bg-green-900/30 border-green-500/50 text-green-400"
                    : "bg-gray-700/30 border-gray-500/50 text-gray-400"
                }`}
              >
                {stats.enabled ? "ACTIVE" : "STANDBY"}
              </span>
            </div>
            <p className="text-sm text-text-secondary">
              {description}
            </p>
            <p className="text-xs text-text-muted italic mt-1">
              {tooltip}
            </p>
          </div>
        </div>

        <button
          onClick={onToggle}
          disabled={isToggling}
          className={`p-2 rounded-lg border transition-all ${
            stats.enabled
              ? "bg-green-900/30 border-green-500/50 text-green-400 hover:bg-green-900/50"
              : "bg-gray-700/30 border-gray-500/50 text-gray-400 hover:bg-gray-700/50"
          }`}
          title={stats.enabled ? "Disable module" : "Enable module"}
        >
          {isToggling ? (
            <Activity className="w-5 h-5 animate-spin" />
          ) : (
            <Power className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t border-border/30">
        <Metric
          label="OPERATIONS"
          value={stats.trades_count.toString()}
          icon={<Activity className="w-4 h-4" />}
        />
        <Metric
          label="WIN RATE"
          value={`${(stats.win_rate * 100).toFixed(0)}%`}
          icon={<Percent className="w-4 h-4" />}
          color={stats.win_rate >= 0.5 ? "green" : "red"}
        />
        <Metric
          label="NET P&L"
          value={`${stats.total_pnl >= 0 ? '+' : ''}${stats.total_pnl.toFixed(2)} SOL`}
          icon={<DollarSign className="w-4 h-4" />}
          color={stats.total_pnl >= 0 ? "green" : "red"}
        />
        <Metric
          label="AVG HOLD"
          value={`${Math.floor(stats.avg_hold_time / 60)}m`}
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Win/Loss Breakdown */}
      {stats.trades_count > 0 && (
        <div className="mt-4 pt-4 border-t border-border/30">
          <div className="flex items-center gap-4 text-sm font-mono">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-400" />
              <span className="text-text-secondary">
                Wins: <span className="text-green-400">{stats.wins}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-red-400" />
              <span className="text-text-secondary">
                Losses: <span className="text-red-400">{stats.losses}</span>
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-blue-400" />
              <span className="text-text-secondary">
                Avg Confidence: <span className="text-blue-400">{(stats.confidence_avg * 100).toFixed(0)}%</span>
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface MetricProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: "green" | "red";
}

function Metric({ label, value, icon, color }: MetricProps) {
  const textColor = color === "green"
    ? "text-green-400"
    : color === "red"
    ? "text-red-400"
    : "text-text-primary";

  return (
    <div>
      <div className="flex items-center gap-1 mb-1 text-text-muted">
        {icon}
        <span className="text-xs font-mono uppercase">
          {label}
        </span>
      </div>
      <div className={`text-lg font-bold font-mono ${textColor}`}>
        {value}
      </div>
    </div>
  );
}
