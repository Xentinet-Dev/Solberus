"use client";

import { useState, useEffect } from "react";
import {
  Package,
  TrendingUp,
  TrendingDown,
  Clock,
  Target,
  AlertTriangle,
  Activity,
  DollarSign,
  Percent,
  ExternalLink,
  XCircle,
  Shield,
  Zap,
} from "lucide-react";

interface Position {
  id: string;
  token_address: string;
  token_symbol: string;
  strategy: string;
  entry_price: number;
  current_price: number;
  amount: number;
  entry_time: number;
  hold_time: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  security_score: number;
  threat_level: "safe" | "low" | "medium" | "high" | "critical";
  stop_loss?: number;
  take_profit?: number;
  confidence: number;
}

interface PortfolioStats {
  total_positions: number;
  total_value_sol: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_percent: number;
  winning_positions: number;
  losing_positions: number;
  avg_hold_time: number;
  at_risk_count: number;
}

export function PositionsTab() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [closingPosition, setClosingPosition] = useState<string | null>(null);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 2000); // Poll every 2s for real-time updates
    return () => clearInterval(interval);
  }, []);

  const fetchPositions = async () => {
    try {
      const response = await fetch("/api/positions/active");
      if (response.ok) {
        const data = await response.json();
        setPositions(data.positions || []);
        setPortfolio(data.portfolio || null);
      }
    } catch (error) {
      console.error("Failed to fetch positions:", error);
    } finally {
      setLoading(false);
    }
  };

  const closePosition = async (positionId: string) => {
    setClosingPosition(positionId);
    try {
      const response = await fetch("/api/positions/close", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ position_id: positionId }),
      });

      if (response.ok) {
        await fetchPositions();
      }
    } catch (error) {
      console.error("Failed to close position:", error);
    } finally {
      setClosingPosition(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-text-secondary">
          <Activity className="w-5 h-5 animate-pulse" />
          <span className="font-mono">LOADING ASSET TRACKING...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border border-purple-500/30 bg-gradient-to-r from-purple-900/20 to-bg-tertiary rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <Package className="w-7 h-7 text-purple-500" />
          <h1 className="text-2xl font-bold tracking-wide text-text-primary font-mono">
            ASSET TRACKING
          </h1>
        </div>
        <p className="text-sm text-text-secondary font-mono">
          LIVE POSITION MONITORING // REAL-TIME P&L // THREAT ASSESSMENT
        </p>
      </div>

      {/* Portfolio Stats */}
      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            label="ACTIVE POSITIONS"
            value={portfolio.total_positions.toString()}
            icon={<Package className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            label="PORTFOLIO VALUE"
            value={`${portfolio.total_value_sol.toFixed(2)} SOL`}
            icon={<DollarSign className="w-5 h-5" />}
            color="purple"
          />
          <StatCard
            label="UNREALIZED P&L"
            value={`${portfolio.total_unrealized_pnl >= 0 ? '+' : ''}${portfolio.total_unrealized_pnl.toFixed(2)} SOL`}
            icon={portfolio.total_unrealized_pnl >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
            color={portfolio.total_unrealized_pnl >= 0 ? "green" : "red"}
          />
          <StatCard
            label="AT RISK"
            value={portfolio.at_risk_count.toString()}
            icon={<AlertTriangle className="w-5 h-5" />}
            color={portfolio.at_risk_count > 0 ? "red" : "green"}
          />
        </div>
      )}

      {/* Win/Loss Breakdown */}
      {portfolio && portfolio.total_positions > 0 && (
        <div className="grid grid-cols-2 gap-4">
          <div className="border border-green-500/30 bg-green-900/10 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-mono text-text-muted uppercase mb-1">
                  WINNING POSITIONS
                </div>
                <div className="text-2xl font-bold font-mono text-green-400">
                  {portfolio.winning_positions}
                </div>
              </div>
              <TrendingUp className="w-8 h-8 text-green-400/50" />
            </div>
          </div>
          <div className="border border-red-500/30 bg-red-900/10 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs font-mono text-text-muted uppercase mb-1">
                  LOSING POSITIONS
                </div>
                <div className="text-2xl font-bold font-mono text-red-400">
                  {portfolio.losing_positions}
                </div>
              </div>
              <TrendingDown className="w-8 h-8 text-red-400/50" />
            </div>
          </div>
        </div>
      )}

      {/* Positions List */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-text-primary font-mono tracking-wide">
          ACTIVE HOLDINGS
        </h2>

        {positions.length === 0 ? (
          <div className="border border-border rounded-lg p-8 text-center">
            <Package className="w-12 h-12 text-text-muted mx-auto mb-3" />
            <p className="text-text-secondary font-mono">
              No active positions.
            </p>
            <p className="text-sm text-text-muted italic mt-1">
              Deploy strategies to start trading. Or keep sitting on SOL.
            </p>
          </div>
        ) : (
          positions.map((position) => (
            <PositionCard
              key={position.id}
              position={position}
              onClose={() => closePosition(position.id)}
              isClosing={closingPosition === position.id}
            />
          ))
        )}
      </div>

      {/* Risk Warning */}
      {portfolio && portfolio.at_risk_count > 0 && (
        <div className="border border-red-500/30 bg-red-900/10 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500 mt-0.5" />
            <div>
              <p className="text-sm text-text-secondary leading-relaxed">
                <span className="font-mono text-red-500">
                  {portfolio.at_risk_count} position(s) showing critical threats.
                </span>
                {" "}
                Rug pull detection, honeypot indicators, or security degradation detected.
                {" "}
                <span className="text-text-muted italic">
                  Exit before it's too late. Or ride it to zero for the screenshot.
                </span>
              </p>
            </div>
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
  color: "blue" | "green" | "red" | "yellow" | "purple";
}

function StatCard({ label, value, icon, color }: StatCardProps) {
  const colorClasses = {
    blue: "border-blue-500/30 bg-blue-900/10 text-blue-400",
    green: "border-green-500/30 bg-green-900/10 text-green-400",
    red: "border-red-500/30 bg-red-900/10 text-red-400",
    yellow: "border-yellow-500/30 bg-yellow-900/10 text-yellow-400",
    purple: "border-purple-500/30 bg-purple-900/10 text-purple-400",
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

interface PositionCardProps {
  position: Position;
  onClose: () => void;
  isClosing: boolean;
}

function PositionCard({ position, onClose, isClosing }: PositionCardProps) {
  const isProfitable = position.unrealized_pnl > 0;
  const isAtRisk = position.threat_level === "high" || position.threat_level === "critical";

  const threatConfig = {
    safe: { color: "green", label: "SAFE", icon: <Shield className="w-4 h-4" /> },
    low: { color: "blue", label: "LOW RISK", icon: <Shield className="w-4 h-4" /> },
    medium: { color: "yellow", label: "MEDIUM RISK", icon: <AlertTriangle className="w-4 h-4" /> },
    high: { color: "orange", label: "HIGH RISK", icon: <AlertTriangle className="w-4 h-4" /> },
    critical: { color: "red", label: "CRITICAL", icon: <AlertTriangle className="w-4 h-4 animate-pulse" /> },
  };

  const threat = threatConfig[position.threat_level];

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m`;
    return `${seconds}s`;
  };

  const getBorderColor = () => {
    if (isAtRisk) return "border-red-500/50";
    if (isProfitable) return "border-green-500/30";
    return "border-red-500/30";
  };

  return (
    <div
      className={`border ${getBorderColor()} bg-bg-tertiary rounded-lg p-6 transition-all hover:border-opacity-80`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-4">
          <div className={`${isProfitable ? "text-green-400" : "text-red-400"} mt-1`}>
            {isProfitable ? <TrendingUp className="w-6 h-6" /> : <TrendingDown className="w-6 h-6" />}
          </div>
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h3 className="text-lg font-bold font-mono text-text-primary">
                {position.token_symbol || position.token_address.slice(0, 8)}
              </h3>
              <span className="px-2 py-0.5 text-xs font-mono border border-blue-500/30 bg-blue-900/10 text-blue-400 rounded">
                {position.strategy.toUpperCase()}
              </span>
              <span
                className={`px-2 py-0.5 text-xs font-mono border rounded ${
                  threat.color === "green"
                    ? "border-green-500/30 bg-green-900/10 text-green-400"
                    : threat.color === "red"
                    ? "border-red-500/30 bg-red-900/10 text-red-400 animate-pulse"
                    : threat.color === "orange"
                    ? "border-orange-500/30 bg-orange-900/10 text-orange-400"
                    : "border-yellow-500/30 bg-yellow-900/10 text-yellow-400"
                }`}
              >
                {threat.label}
              </span>
            </div>
            <a
              href={`https://solscan.io/token/${position.token_address}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono text-text-muted hover:text-cyan-400 flex items-center gap-1"
            >
              {position.token_address}
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>

        {/* Unrealized P&L */}
        <div className="text-right">
          <div className={`text-2xl font-bold font-mono ${isProfitable ? "text-green-400" : "text-red-400"}`}>
            {isProfitable ? "+" : ""}{position.unrealized_pnl.toFixed(4)} SOL
          </div>
          <div className={`text-sm font-mono ${isProfitable ? "text-green-400/70" : "text-red-400/70"}`}>
            {isProfitable ? "+" : ""}{position.unrealized_pnl_percent.toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Position Details */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <Metric
          label="ENTRY PRICE"
          value={`${position.entry_price.toFixed(8)}`}
          icon={<Target className="w-4 h-4" />}
        />
        <Metric
          label="CURRENT PRICE"
          value={`${position.current_price.toFixed(8)}`}
          icon={<Activity className="w-4 h-4" />}
        />
        <Metric
          label="POSITION SIZE"
          value={`${position.amount.toFixed(2)} SOL`}
          icon={<DollarSign className="w-4 h-4" />}
        />
        <Metric
          label="HOLD TIME"
          value={formatDuration(position.hold_time)}
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Stop Loss / Take Profit */}
      {(position.stop_loss || position.take_profit) && (
        <div className="border-t border-border/30 pt-4 mb-4">
          <div className="flex items-center gap-6 text-sm font-mono">
            {position.stop_loss && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted">STOP LOSS:</span>
                <span className="text-red-400">{position.stop_loss.toFixed(8)}</span>
              </div>
            )}
            {position.take_profit && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted">TAKE PROFIT:</span>
                <span className="text-green-400">{position.take_profit.toFixed(8)}</span>
              </div>
            )}
            <div className="flex items-center gap-2">
              <span className="text-text-muted">CONFIDENCE:</span>
              <span className="text-blue-400">{(position.confidence * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="border-t border-border/30 pt-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-text-muted" />
          <span className="text-xs font-mono text-text-muted">
            Security Score: <span className={position.security_score >= 70 ? "text-green-400" : position.security_score >= 50 ? "text-yellow-400" : "text-red-400"}>{position.security_score}/100</span>
          </span>
        </div>

        <button
          onClick={onClose}
          disabled={isClosing}
          className="flex items-center gap-2 px-4 py-2 bg-red-900/30 border border-red-500/50 rounded-lg text-red-400 hover:bg-red-900/50 transition-all font-mono text-sm disabled:opacity-50"
          title={isAtRisk ? "EXIT IMMEDIATELY. Serious threats detected." : "Close position and realize P&L"}
        >
          {isClosing ? (
            <>
              <Activity className="w-4 h-4 animate-spin" />
              CLOSING...
            </>
          ) : (
            <>
              <XCircle className="w-4 h-4" />
              {isAtRisk ? "EMERGENCY EXIT" : "CLOSE POSITION"}
            </>
          )}
        </button>
      </div>

      {/* Risk Warning */}
      {isAtRisk && (
        <div className="mt-4 pt-4 border-t border-red-500/30">
          <p className="text-xs text-red-400 italic">
            {position.threat_level === "critical"
              ? "CRITICAL THREAT. Honeypot, rug pull, or security exploit detected. Exit NOW."
              : "High-risk indicators detected. Consider closing this position before it rugs."}
          </p>
        </div>
      )}

      {/* Profit Commentary */}
      {!isAtRisk && isProfitable && position.unrealized_pnl_percent > 30 && (
        <div className="mt-4 pt-4 border-t border-border/30">
          <p className="text-xs text-green-400/70 italic">
            +{position.unrealized_pnl_percent.toFixed(0)}% unrealized. Take profit before the whales dump on you.
          </p>
        </div>
      )}
      {!isAtRisk && !isProfitable && position.unrealized_pnl_percent < -20 && (
        <div className="mt-4 pt-4 border-t border-border/30">
          <p className="text-xs text-red-400/70 italic">
            Down {Math.abs(position.unrealized_pnl_percent).toFixed(0)}%. Cut losses or pray for a reversal.
          </p>
        </div>
      )}
    </div>
  );
}

interface MetricProps {
  label: string;
  value: string;
  icon: React.ReactNode;
}

function Metric({ label, value, icon }: MetricProps) {
  return (
    <div>
      <div className="flex items-center gap-1 mb-1 text-text-muted">
        {icon}
        <span className="text-xs font-mono uppercase">
          {label}
        </span>
      </div>
      <div className="text-sm font-bold font-mono text-text-primary">
        {value}
      </div>
    </div>
  );
}
