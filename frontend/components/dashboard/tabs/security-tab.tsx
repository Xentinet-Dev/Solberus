"use client";

import { useState } from "react";
import {
  Shield,
  AlertTriangle,
  XCircle,
  CheckCircle,
  Search,
  AlertOctagon,
  Skull,
  Bug,
  Eye,
  Lock,
  Zap,
} from "lucide-react";

interface ThreatDetection {
  category: string;
  severity: "critical" | "high" | "medium" | "low";
  description: string;
  confidence: number;
  evidence: Record<string, any>;
}

interface SecurityScanResult {
  token_address: string;
  health_score: number; // 0-100
  risk_level: "safe" | "low" | "medium" | "high" | "critical";
  threats_detected: ThreatDetection[];
  scan_time: string;
}

export function SecurityTab() {
  const [tokenAddress, setTokenAddress] = useState("");
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<SecurityScanResult | null>(null);

  const handleScan = async () => {
    if (!tokenAddress.trim()) return;

    setIsScanning(true);
    try {
      const response = await fetch("/api/security/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token_address: tokenAddress }),
      });

      if (response.ok) {
        const data = await response.json();
        setScanResult(data);
      }
    } catch (error) {
      console.error("Security scan failed:", error);
    } finally {
      setIsScanning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* THREAT SCANNER HEADER */}
      <div className="border border-red-500/30 bg-gradient-to-r from-red-900/20 to-bg-tertiary rounded-lg p-6">
        <div className="flex items-center gap-3 mb-2">
          <AlertOctagon className="w-7 h-7 text-red-500" />
          <h1 className="text-2xl font-bold tracking-wide text-text-primary font-mono">
            THREAT MATRIX SCANNER
          </h1>
        </div>
        <p className="text-sm text-text-secondary font-mono">
          ANALYZING 94+ ATTACK VECTORS // TRUST NOTHING
        </p>
      </div>

      {/* SCANNER INPUT */}
      <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
        <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
          INITIATE DEEP SCAN
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-text-muted mb-2 font-mono">
              TARGET TOKEN ADDRESS
            </label>
            <div className="flex gap-3">
              <input
                type="text"
                value={tokenAddress}
                onChange={(e) => setTokenAddress(e.target.value)}
                placeholder="Enter Solana token address..."
                className="flex-1 px-4 py-3 bg-bg-secondary border border-border-muted rounded font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-primary transition-colors"
              />
              <button
                onClick={handleScan}
                disabled={isScanning || !tokenAddress.trim()}
                className="px-6 py-3 bg-gradient-to-r from-red-900/30 to-red-800/20 border-2 border-red-500/50 rounded font-mono font-bold text-red-400 hover:bg-red-900/50 hover:border-red-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                title="Scan for honeypots, rug pulls, and other creative ways to lose money."
              >
                <Search className="w-4 h-4" />
                {isScanning ? "SCANNING..." : "ANALYZE"}
              </button>
            </div>
          </div>

          <div className="border-l-4 border-amber-500 bg-amber-900/10 p-3">
            <p className="text-xs text-text-secondary">
              <span className="font-mono font-bold text-amber-400">ADVISORY:</span>
              {" "}
              Scans check for 94+ threat categories. Still won't save you from copy-paste errors.
            </p>
          </div>
        </div>
      </div>

      {/* SCAN RESULTS */}
      {scanResult && (
        <>
          {/* HEALTH SCORE */}
          <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
            <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
              THREAT ASSESSMENT
            </h2>

            <div className="grid grid-cols-3 gap-4 mb-6">
              {/* Health Score */}
              <div className="col-span-2">
                <HealthScoreDisplay
                  score={scanResult.health_score}
                  riskLevel={scanResult.risk_level}
                />
              </div>

              {/* Quick Stats */}
              <div className="space-y-3">
                <StatBox
                  label="THREATS"
                  value={scanResult.threats_detected.length.toString()}
                  color={scanResult.threats_detected.length > 0 ? "red" : "green"}
                  tooltip="Number of detected threats. Zero is good. Anything else, not so much."
                />
                <StatBox
                  label="SCAN TIME"
                  value={new Date(scanResult.scan_time).toLocaleTimeString()}
                  color="gray"
                  tooltip="When we last checked. Threats can evolve. Stay paranoid."
                />
              </div>
            </div>

            {/* Risk Level Banner */}
            <RiskLevelBanner riskLevel={scanResult.risk_level} />
          </div>

          {/* DETECTED THREATS */}
          <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
            <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
              DETECTED THREATS
            </h2>

            {scanResult.threats_detected.length > 0 ? (
              <div className="space-y-3">
                {scanResult.threats_detected.map((threat, index) => (
                  <ThreatCard key={index} threat={threat} />
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-3" />
                <p className="font-mono text-green-500 font-bold mb-2">
                  NO THREATS DETECTED
                </p>
                <p className="text-sm text-text-muted">
                  Either this token is clean, or the scammers got creative.
                  {" "}
                  <span className="italic">Probably the latter.</span>
                </p>
              </div>
            )}
          </div>

          {/* THREAT CATEGORIES BREAKDOWN */}
          <div className="border border-border-muted rounded-lg bg-bg-tertiary p-6">
            <h2 className="text-lg font-bold mb-4 text-text-primary font-mono tracking-wide">
              THREAT CATEGORY STATUS
            </h2>

            <div className="grid grid-cols-2 gap-3">
              <ThreatCategory
                name="HONEYPOT DETECTION"
                icon={<Bug className="w-4 h-4" />}
                status="checked"
                description="Sell function analysis"
                tooltip="Checks if you can actually sell. Because some devs 'forget' to code that part."
              />
              <ThreatCategory
                name="RUG PULL ANALYSIS"
                icon={<Skull className="w-4 h-4" />}
                status="checked"
                description="Creator behavior patterns"
                tooltip="Serial ruggers detected. They've done this before. They'll do it again."
              />
              <ThreatCategory
                name="LIQUIDITY MONITOR"
                icon={<Eye className="w-4 h-4" />}
                status="checked"
                description="LP token tracking"
                tooltip="Watching the liquidity like a hawk. Or trying to, at least."
              />
              <ThreatCategory
                name="WASH TRADING"
                icon={<AlertTriangle className="w-4 h-4" />}
                status="checked"
                description="Volume authenticity"
                tooltip="Fake volume detection. Most of it is bots trading with themselves."
              />
              <ThreatCategory
                name="ORACLE MANIPULATION"
                icon={<Lock className="w-4 h-4" />}
                status="checked"
                description="Price feed integrity"
                tooltip="Oracle desync, staleness, manipulation. The fun stuff."
              />
              <ThreatCategory
                name="TOKEN-2022 EXPLOITS"
                icon={<Shield className="w-4 h-4" />}
                status="checked"
                description="Extension abuse detection"
                tooltip="Transfer hooks, permanent delegates. New tech, same scams."
              />
              <ThreatCategory
                name="PUMP & DUMP"
                icon={<AlertOctagon className="w-4 h-4" />}
                status="checked"
                description="Price manipulation"
                tooltip="Detect coordinated pumps. Whales accumulate, retail FOMO, whales dump. Classic."
              />
              <ThreatCategory
                name="FLASH LOAN ATTACKS"
                icon={<Zap className="w-4 h-4" />}
                status="checked"
                description="Borrow-manipulate-repay"
                tooltip="Manipulate price with borrowed funds. Profitable and probably illegal."
              />
            </div>
          </div>
        </>
      )}

      {/* EMPTY STATE */}
      {!scanResult && !isScanning && (
        <div className="border border-border-muted rounded-lg bg-bg-tertiary p-12 text-center">
          <Shield className="w-16 h-16 text-text-muted mx-auto mb-4 opacity-50" />
          <h3 className="font-mono font-bold text-text-primary mb-2">
            SCANNER ON STANDBY
          </h3>
          <p className="text-sm text-text-secondary max-w-md mx-auto">
            Enter a token address above to begin threat analysis.
            {" "}
            <span className="text-text-muted italic">
              We'll tell you if it's a honeypot. We can't stop you from buying it anyway.
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

// Helper Components
function HealthScoreDisplay({ score, riskLevel }: { score: number; riskLevel: string }) {
  const getColor = () => {
    if (score >= 80) return "text-green-500";
    if (score >= 60) return "text-yellow-500";
    if (score >= 40) return "text-orange-500";
    return "text-red-500";
  };

  const getBarColor = () => {
    if (score >= 80) return "bg-green-500";
    if (score >= 60) return "bg-yellow-500";
    if (score >= 40) return "bg-orange-500";
    return "bg-red-500";
  };

  return (
    <div className="border border-border-muted rounded-lg bg-bg-secondary p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs uppercase tracking-wider text-text-muted font-mono">
          SECURITY HEALTH SCORE
        </div>
        <div className={`text-3xl font-bold font-mono ${getColor()}`}>
          {score}/100
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-3 bg-bg-tertiary rounded-full overflow-hidden mb-3">
        <div
          className={`h-full ${getBarColor()} transition-all duration-500`}
          style={{ width: `${score}%` }}
        />
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted font-mono">CRITICAL</span>
        <span className="text-text-muted font-mono">SAFE</span>
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  color,
  tooltip,
}: {
  label: string;
  value: string;
  color: "red" | "green" | "gray";
  tooltip: string;
}) {
  const colorClasses = {
    red: "border-red-500/50 bg-red-900/10 text-red-400",
    green: "border-green-500/50 bg-green-900/10 text-green-400",
    gray: "border-border-muted bg-bg-secondary text-text-primary",
  };

  return (
    <div
      className={`border rounded-lg p-3 ${colorClasses[color]} cursor-help`}
      title={tooltip}
    >
      <div className="text-xs uppercase tracking-wider text-text-muted mb-1 font-mono">
        {label}
      </div>
      <div className="text-lg font-bold font-mono">{value}</div>
    </div>
  );
}

function RiskLevelBanner({ riskLevel }: { riskLevel: string }) {
  const config = {
    safe: {
      color: "green",
      border: "border-green-500",
      bg: "bg-green-900/20",
      text: "text-green-400",
      message: "No major threats detected. Still DYOR.",
    },
    low: {
      color: "yellow",
      border: "border-yellow-500",
      bg: "bg-yellow-900/20",
      text: "text-yellow-400",
      message: "Minor concerns. Proceed with caution and small bags.",
    },
    medium: {
      color: "orange",
      border: "border-orange-500",
      bg: "bg-orange-900/20",
      text: "text-orange-400",
      message: "Multiple threats detected. High risk, probably not worth it.",
    },
    high: {
      color: "red",
      border: "border-red-500",
      bg: "bg-red-900/20",
      text: "text-red-400",
      message: "Serious threats detected. Exit if holding. Don't enter if not.",
    },
    critical: {
      color: "red",
      border: "border-red-600",
      bg: "bg-red-950/50",
      text: "text-red-500",
      message: "CRITICAL THREATS. Honeypot or rug imminent. RUN.",
    },
  };

  const cfg = config[riskLevel as keyof typeof config] || config.medium;

  return (
    <div className={`border-l-4 ${cfg.border} ${cfg.bg} p-4`}>
      <div className="flex items-center gap-3">
        <AlertTriangle className={`w-5 h-5 ${cfg.text} flex-shrink-0`} />
        <div>
          <h3 className={`font-mono font-bold ${cfg.text} text-sm mb-1`}>
            RISK LEVEL: {riskLevel.toUpperCase()}
          </h3>
          <p className="text-sm text-text-secondary">{cfg.message}</p>
        </div>
      </div>
    </div>
  );
}

function ThreatCard({ threat }: { threat: ThreatDetection }) {
  const severityConfig = {
    critical: {
      icon: <XCircle className="w-5 h-5" />,
      color: "text-red-500",
      border: "border-red-500/50",
      bg: "bg-red-900/10",
    },
    high: {
      icon: <AlertTriangle className="w-5 h-5" />,
      color: "text-orange-500",
      border: "border-orange-500/50",
      bg: "bg-orange-900/10",
    },
    medium: {
      icon: <AlertOctagon className="w-5 h-5" />,
      color: "text-yellow-500",
      border: "border-yellow-500/50",
      bg: "bg-yellow-900/10",
    },
    low: {
      icon: <AlertTriangle className="w-5 h-5" />,
      color: "text-blue-500",
      border: "border-blue-500/50",
      bg: "bg-blue-900/10",
    },
  };

  const cfg = severityConfig[threat.severity];

  return (
    <div className={`border ${cfg.border} ${cfg.bg} rounded-lg p-4`}>
      <div className="flex items-start gap-3">
        <div className={cfg.color}>{cfg.icon}</div>
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-mono font-bold text-text-primary text-sm">
              {threat.category.replace(/_/g, " ").toUpperCase()}
            </h4>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted font-mono">
                {(threat.confidence * 100).toFixed(0)}% CONFIDENCE
              </span>
              <span className={`text-xs font-mono font-bold ${cfg.color} uppercase`}>
                {threat.severity}
              </span>
            </div>
          </div>
          <p className="text-sm text-text-secondary mb-2">{threat.description}</p>
          {Object.keys(threat.evidence).length > 0 && (
            <details className="text-xs text-text-muted">
              <summary className="cursor-pointer font-mono hover:text-text-secondary">
                [ VIEW EVIDENCE ]
              </summary>
              <pre className="mt-2 p-2 bg-bg-tertiary rounded font-mono text-xs overflow-x-auto">
                {JSON.stringify(threat.evidence, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function ThreatCategory({
  name,
  icon,
  status,
  description,
  tooltip,
}: {
  name: string;
  icon: React.ReactNode;
  status: "checked" | "unchecked";
  description: string;
  tooltip: string;
}) {
  return (
    <div
      className="border border-border-muted bg-bg-secondary rounded-lg p-3 hover:border-accent-primary/50 transition-colors cursor-help"
      title={tooltip}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="text-accent-primary">{icon}</div>
        <h4 className="font-mono font-bold text-xs text-text-primary">{name}</h4>
        <CheckCircle className="w-4 h-4 text-green-500 ml-auto" />
      </div>
      <p className="text-xs text-text-secondary">{description}</p>
    </div>
  );
}
