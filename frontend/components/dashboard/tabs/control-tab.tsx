"use client";

import { useState, useEffect } from "react";
import { Play, Square, Activity, Shield, Zap, AlertTriangle } from "lucide-react";

interface BotStatus {
  bot_id: string;
  status: "active" | "inactive" | "error";
  uptime: number;
  strategies_enabled: string[];
  capital_deployed: number;
  positions_open: number;
  last_action: string;
}

export function ControlTab() {
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  // Fetch bot status
  const fetchStatus = async () => {
    try {
      // TODO: Replace with actual bot_id from user's active bots
      const response = await fetch("/api/bot/status/primary");
      if (response.ok) {
        const data = await response.json();
        setBotStatus(data);
      }
    } catch (error) {
      console.error("Failed to fetch bot status:", error);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000); // Poll every 3s
    return () => clearInterval(interval);
  }, []);

  const handleStartBot = async () => {
    setIsStarting(true);
    try {
      const response = await fetch("/api/bot/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          strategy: "multi",
          capital: 100.0,
          config: {
            strategies: ["snipe", "momentum", "reversal", "whale_copy", "social_signals"],
          },
        }),
      });

      if (response.ok) {
        const data = await response.json();
        console.log("Bot started:", data);
        await fetchStatus();
      }
    } catch (error) {
      console.error("Failed to start bot:", error);
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopBot = async () => {
    if (!botStatus?.bot_id) return;

    setIsStopping(true);
    try {
      const response = await fetch(`/api/bot/stop/${botStatus.bot_id}`, {
        method: "POST",
      });

      if (response.ok) {
        await fetchStatus();
      }
    } catch (error) {
      console.error("Failed to stop bot:", error);
    } finally {
      setIsStopping(false);
    }
  };

  const isActive = botStatus?.status === "active";
  const isError = botStatus?.status === "error";

  return (
    <div className="space-y-6">
      {/* OPERATION STATUS HEADER */}
      <div className="border border-border-muted bg-gradient-to-r from-bg-tertiary to-bg-secondary rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Shield className="w-6 h-6 text-accent-primary" />
              <h1 className="text-2xl font-bold tracking-wide text-text-primary font-mono">
                OPERATION CONTROL
              </h1>
            </div>
            <p className="text-sm text-text-secondary font-mono">
              SENTINEL NODE // TACTICAL TRADING SYSTEM
            </p>
          </div>

          {/* STATUS INDICATOR */}
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs text-text-muted uppercase tracking-wider mb-1">
                System Status
              </div>
              <div className="flex items-center gap-2">
                <div
                  className={`w-2 h-2 rounded-full ${
                    isActive
                      ? "bg-green-500 animate-pulse"
                      : isError
                      ? "bg-red-500 animate-pulse"
                      : "bg-gray-600"
                  }`}
                />
                <span
                  className={`font-mono text-sm font-semibold ${
                    isActive
                      ? "text-green-500"
                      : isError
                      ? "text-red-500"
                      : "text-text-muted"
                  }`}
                >
                  {isActive ? "OPERATIONAL" : isError ? "FAULT" : "STANDBY"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SYSTEM METRICS */}
      {botStatus && isActive && (
        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            icon={<Activity className="w-5 h-5" />}
            label="UPTIME"
            value={formatUptime(botStatus.uptime)}
            tooltip="Time since deployment. Restarts are for cowards."
          />
          <MetricCard
            icon={<Zap className="w-5 h-5" />}
            label="STRATEGIES"
            value={botStatus.strategies_enabled.length.toString()}
            tooltip="Active defense modules. More shields, less rugs."
          />
          <MetricCard
            icon={<Shield className="w-5 h-5" />}
            label="CAPITAL"
            value={`${botStatus.capital_deployed.toFixed(2)} SOL`}
            tooltip="Assets under management. Not financial advice, obviously."
          />
          <MetricCard
            icon={<AlertTriangle className="w-5 h-5" />}
            label="POSITIONS"
            value={botStatus.positions_open.toString()}
            tooltip="Open trades. Pray they're not honeypots."
          />
        </div>
      )}

      {/* DEPLOYMENT CONTROLS */}
      <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
        <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
          DEPLOYMENT AUTHORIZATION
        </h2>

        <div className="space-y-4">
          {/* Deploy/Terminate Buttons */}
          <div className="flex gap-4">
            <button
              onClick={handleStartBot}
              disabled={isActive || isStarting}
              className="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-gradient-to-r from-green-900/30 to-green-800/20 border-2 border-green-500/50 rounded-lg font-mono font-bold text-green-400 hover:bg-green-900/50 hover:border-green-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-green-900/30 group"
              title="Initialize sentinel node and commence operations. No refunds."
            >
              <Play className="w-5 h-5 group-hover:animate-pulse" />
              {isStarting ? "DEPLOYING..." : "DEPLOY SENTINEL"}
            </button>

            <button
              onClick={handleStopBot}
              disabled={!isActive || isStopping}
              className="flex-1 flex items-center justify-center gap-3 px-6 py-4 bg-gradient-to-r from-red-900/30 to-red-800/20 border-2 border-red-500/50 rounded-lg font-mono font-bold text-red-400 hover:bg-red-900/50 hover:border-red-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-red-900/30 group"
              title="Emergency stop. Close all positions and retreat. Losses not covered."
            >
              <Square className="w-5 h-5 group-hover:animate-pulse" />
              {isStopping ? "TERMINATING..." : "TERMINATE"}
            </button>
          </div>

          {/* Warning Notice */}
          <div className="border-l-4 border-amber-500 bg-amber-900/10 p-4">
            <div className="flex gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-mono font-bold text-amber-400 text-sm mb-1">
                  OPERATIONAL ADVISORY
                </h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  Live trading on Solana. Expect rug pulls, honeypots, and serial scammers.
                  {" "}
                  <span className="text-text-muted italic">
                    We detect threats, but Darwin still applies.
                  </span>
                </p>
              </div>
            </div>
          </div>

          {/* Last Action */}
          {botStatus?.last_action && (
            <div className="border border-border-muted rounded bg-bg-secondary p-3">
              <div className="text-xs text-text-muted uppercase tracking-wider mb-1 font-mono">
                LAST ACTION
              </div>
              <div className="text-sm text-text-primary font-mono">
                {botStatus.last_action}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* STRATEGY CONFIGURATION */}
      <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
        <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
          ACTIVE DEFENSE MODULES
        </h2>

        <div className="grid grid-cols-2 gap-3">
          <DefenseModule
            name="SNIPE PROTOCOL"
            status={botStatus?.strategies_enabled.includes("snipe") ? "active" : "standby"}
            description="Fast entry on token launches"
            tooltip="First blood wins. Sub-second detection before the bots wake up."
          />
          <DefenseModule
            name="MOMENTUM TRACKER"
            status={botStatus?.strategies_enabled.includes("momentum") ? "active" : "standby"}
            description="RSI/MACD technical analysis"
            tooltip="Follow the trend until it rugs. Technical indicators for the illusion of control."
          />
          <DefenseModule
            name="REVERSAL SCANNER"
            status={botStatus?.strategies_enabled.includes("reversal") ? "active" : "standby"}
            description="Buy dips, sell peaks"
            tooltip="Mean reversion. Works until it doesn't. Usually at -50%."
          />
          <DefenseModule
            name="WHALE RECON"
            status={botStatus?.strategies_enabled.includes("whale_copy") ? "active" : "standby"}
            description="Copy successful wallets"
            tooltip="Follow the smart money. Hope they're not smarter at exiting than you."
          />
          <DefenseModule
            name="SOCIAL RADAR"
            status={botStatus?.strategies_enabled.includes("social_signals") ? "active" : "standby"}
            description="Twitter/Telegram signals"
            tooltip="Trade on hype. Filter out the bots. Good luck with that."
          />
          <DefenseModule
            name="THREAT MATRIX"
            status="active"
            description="94+ security checks"
            tooltip="Honeypot detection, rug prediction, wash trading. The scammers are creative."
          />
        </div>
      </div>

      {/* OPERATIONAL PARAMETERS */}
      <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
        <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
          OPERATIONAL PARAMETERS
        </h2>

        <div className="space-y-4">
          <Parameter
            label="RPC ENDPOINT"
            value="Helius RPC // MAINNET-BETA"
            tooltip="Connection to Solana. If this goes down, so do you."
          />
          <Parameter
            label="EXECUTION MODE"
            value="LIVE FIRE // NO SIMULATION"
            tooltip="Real transactions, real money. Testnet is for cowards."
            warning
          />
          <Parameter
            label="RISK TOLERANCE"
            value="AGGRESSIVE // DEGENERATE"
            tooltip="High risk, high reward. Or just high losses. Usually the latter."
            warning
          />
          <Parameter
            label="SLIPPAGE LIMIT"
            value="20% MAX"
            tooltip="How much you're willing to get rugged on entry. Generous."
          />
        </div>
      </div>
    </div>
  );
}

// Helper Components
function MetricCard({
  icon,
  label,
  value,
  tooltip,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tooltip: string;
}) {
  return (
    <div
      className="border border-border-muted bg-bg-secondary rounded-lg p-4 hover:border-accent-primary/50 transition-colors cursor-help group"
      title={tooltip}
    >
      <div className="flex items-center gap-2 mb-2 text-accent-primary">
        {icon}
        <div className="text-xs uppercase tracking-wider text-text-muted font-mono">
          {label}
        </div>
      </div>
      <div className="text-2xl font-bold font-mono text-text-primary group-hover:text-accent-primary transition-colors">
        {value}
      </div>
    </div>
  );
}

function DefenseModule({
  name,
  status,
  description,
  tooltip,
}: {
  name: string;
  status: "active" | "standby";
  description: string;
  tooltip: string;
}) {
  const isActive = status === "active";

  return (
    <div
      className={`border rounded-lg p-4 transition-all cursor-help ${
        isActive
          ? "border-green-500/50 bg-green-900/10"
          : "border-border-muted bg-bg-secondary"
      }`}
      title={tooltip}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-mono font-bold text-sm text-text-primary">{name}</h3>
        <div
          className={`w-2 h-2 rounded-full ${
            isActive ? "bg-green-500 animate-pulse" : "bg-gray-600"
          }`}
        />
      </div>
      <p className="text-xs text-text-secondary">{description}</p>
      <div className="mt-2 text-xs font-mono font-semibold">
        <span className={isActive ? "text-green-500" : "text-text-muted"}>
          {isActive ? "[ ACTIVE ]" : "[ STANDBY ]"}
        </span>
      </div>
    </div>
  );
}

function Parameter({
  label,
  value,
  tooltip,
  warning = false,
}: {
  label: string;
  value: string;
  tooltip: string;
  warning?: boolean;
}) {
  return (
    <div
      className="flex items-center justify-between py-3 border-b border-border-muted last:border-0 cursor-help hover:bg-bg-secondary/50 px-3 -mx-3 transition-colors"
      title={tooltip}
    >
      <div className="text-sm text-text-muted font-mono uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-sm font-mono font-semibold ${
          warning ? "text-amber-400" : "text-text-primary"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  } else if (minutes > 0) {
    return `${minutes}m ${secs}s`;
  } else {
    return `${secs}s`;
  }
}
