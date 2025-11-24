"use client";

import { useState } from "react";
import Tooltip from "@/components/ui/Tooltip";

interface MHTIBucket {
  risk: number;
  technical: number;
  market: number;
}

interface ConfidenceInterval {
  lower: number;
  upper: number;
  uncertainty: "low" | "medium" | "high";
}

interface TopFactor {
  factor: string;
  value: number;
}

interface TrendAnalysis {
  trend: number;
  acceleration: number;
  direction: "increasing" | "decreasing" | "stable" | "unknown";
  confidence: "none" | "insufficient" | "low" | "medium" | "high";
  alert: string | null;
  data_points: number;
}

interface MHTIResult {
  engine: string;
  score: number;
  risk_level: "safe" | "monitor" | "high" | "critical";
  buckets: MHTIBucket;
  top_factors: TopFactor[];
  confidence_interval: ConfidenceInterval;
}

interface MHTIResponse {
  token_address: string;
  mhti: MHTIResult;
  trend?: TrendAnalysis;
  timestamp: number;
}

export default function MultiHeadedThreatIndex() {
  const [tokenAddress, setTokenAddress] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MHTIResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const getRiskLevelColor = (level: string) => {
    switch (level) {
      case "safe":
        return "text-accent-success";
      case "monitor":
        return "text-accent-warning";
      case "high":
        return "text-orange-500";
      case "critical":
        return "text-accent-danger";
      default:
        return "text-text-secondary";
    }
  };

  const getRiskLevelBgColor = (level: string) => {
    switch (level) {
      case "safe":
        return "bg-accent-success/20 border-accent-success";
      case "monitor":
        return "bg-accent-warning/20 border-accent-warning";
      case "high":
        return "bg-orange-500/20 border-orange-500";
      case "critical":
        return "bg-accent-danger/20 border-accent-danger";
      default:
        return "bg-bg-secondary border-border";
    }
  };

  const getUncertaintyColor = (uncertainty: string) => {
    switch (uncertainty) {
      case "low":
        return "text-accent-success";
      case "medium":
        return "text-accent-warning";
      case "high":
        return "text-accent-danger";
      default:
        return "text-text-secondary";
    }
  };

  const getTrendIcon = (direction: string) => {
    switch (direction) {
      case "increasing":
        return "↗";
      case "decreasing":
        return "↘";
      case "stable":
        return "→";
      default:
        return "?";
    }
  };

  const handleScan = async () => {
    if (!tokenAddress.trim()) {
      setError("Please enter a token address");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/security/multi-threat-index`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ token_address: tokenAddress }),
        }
      );

      if (!response.ok) {
        throw new Error(`Scan failed: ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to scan token");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-bg-tertiary border border-border p-6 rounded-lg space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold uppercase tracking-wide">
            Multi-Headed Threat Index (MHTI)
          </h2>
          <p className="text-sm text-text-muted mt-1">
            Unified risk score blending 30+ threat detectors, technical checks, and market health
          </p>
        </div>
        <Tooltip text="The Multi-Headed Threat Index blends 30+ Solberus threat detectors with real technical and market metrics to produce a unified risk score." />
      </div>

      {/* Input Section */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Enter token address..."
          value={tokenAddress}
          onChange={(e) => setTokenAddress(e.target.value)}
          className="flex-1 bg-bg-secondary border border-border rounded-lg px-4 py-2 text-text-primary focus:outline-none focus:border-accent-primary"
          disabled={loading}
        />
        <button
          onClick={handleScan}
          disabled={loading}
          className="px-6 py-2 bg-accent-primary text-white font-bold uppercase rounded-lg hover:bg-accent-primary/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Scanning..." : "Scan"}
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-accent-danger/20 border border-accent-danger rounded-lg p-4">
          <p className="text-accent-danger font-medium">{error}</p>
        </div>
      )}

      {/* Results Display */}
      {result && (
        <div className="space-y-6">
          {/* Risk Score Card */}
          <div
            className={`p-6 rounded-lg border-2 ${getRiskLevelBgColor(
              result.mhti.risk_level
            )}`}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-sm uppercase text-text-muted mb-1">Risk Score</div>
                <div className="text-5xl font-bold">{result.mhti.score.toFixed(3)}</div>
              </div>
              <div className="text-right">
                <div className="text-sm uppercase text-text-muted mb-1">Risk Level</div>
                <div
                  className={`text-2xl font-bold uppercase ${getRiskLevelColor(
                    result.mhti.risk_level
                  )}`}
                >
                  {result.mhti.risk_level}
                </div>
              </div>
            </div>

            {/* Score Bar */}
            <div className="relative h-3 bg-bg-secondary rounded-full overflow-hidden">
              <div
                className={`absolute left-0 top-0 h-full transition-all ${
                  result.mhti.risk_level === "safe"
                    ? "bg-accent-success"
                    : result.mhti.risk_level === "monitor"
                    ? "bg-accent-warning"
                    : result.mhti.risk_level === "high"
                    ? "bg-orange-500"
                    : "bg-accent-danger"
                }`}
                style={{ width: `${result.mhti.score * 100}%` }}
              />
            </div>

            {/* Thresholds */}
            <div className="flex justify-between text-xs text-text-muted mt-2">
              <span>0.0 (Safe)</span>
              <span>0.3 (Monitor)</span>
              <span>0.6 (High)</span>
              <span>1.0 (Critical)</span>
            </div>
          </div>

          {/* Bucket Breakdown */}
          <div className="bg-bg-secondary border border-border rounded-lg p-4">
            <h3 className="text-sm font-bold uppercase text-text-muted mb-4">
              Bucket Breakdown
            </h3>
            <div className="grid grid-cols-3 gap-4">
              {/* Risk Bucket */}
              <div>
                <div className="text-xs uppercase text-text-muted mb-2">
                  Risk Signals (40%)
                </div>
                <div className="h-32 bg-bg-tertiary rounded-lg border border-border relative overflow-hidden">
                  <div
                    className="absolute bottom-0 left-0 right-0 bg-accent-danger transition-all"
                    style={{ height: `${result.mhti.buckets.risk * 100}%` }}
                  />
                </div>
                <div className="text-center mt-2 font-bold">
                  {result.mhti.buckets.risk.toFixed(2)}
                </div>
              </div>

              {/* Technical Bucket */}
              <div>
                <div className="text-xs uppercase text-text-muted mb-2">
                  Technical (30%)
                </div>
                <div className="h-32 bg-bg-tertiary rounded-lg border border-border relative overflow-hidden">
                  <div
                    className="absolute bottom-0 left-0 right-0 bg-accent-warning transition-all"
                    style={{ height: `${result.mhti.buckets.technical * 100}%` }}
                  />
                </div>
                <div className="text-center mt-2 font-bold">
                  {result.mhti.buckets.technical.toFixed(2)}
                </div>
              </div>

              {/* Market Bucket */}
              <div>
                <div className="text-xs uppercase text-text-muted mb-2">
                  Market Health (30%)
                </div>
                <div className="h-32 bg-bg-tertiary rounded-lg border border-border relative overflow-hidden">
                  <div
                    className="absolute bottom-0 left-0 right-0 bg-accent-primary transition-all"
                    style={{ height: `${result.mhti.buckets.market * 100}%` }}
                  />
                </div>
                <div className="text-center mt-2 font-bold">
                  {result.mhti.buckets.market.toFixed(2)}
                </div>
              </div>
            </div>
          </div>

          {/* Top Contributing Factors */}
          <div className="bg-bg-secondary border border-border rounded-lg p-4">
            <h3 className="text-sm font-bold uppercase text-text-muted mb-3">
              Top Contributing Factors
            </h3>
            <div className="space-y-2">
              {result.mhti.top_factors.map((factor, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm capitalize">{factor.factor}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 h-2 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent-primary transition-all"
                        style={{ width: `${factor.value * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-mono w-12 text-right">
                      {factor.value.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Confidence Interval */}
          <div className="bg-bg-secondary border border-border rounded-lg p-4">
            <h3 className="text-sm font-bold uppercase text-text-muted mb-3">
              Confidence Interval
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-text-muted">Lower Bound</div>
                <div className="text-lg font-mono">
                  {result.mhti.confidence_interval.lower.toFixed(3)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-text-muted">Uncertainty</div>
                <div
                  className={`text-lg font-bold uppercase ${getUncertaintyColor(
                    result.mhti.confidence_interval.uncertainty
                  )}`}
                >
                  {result.mhti.confidence_interval.uncertainty}
                </div>
              </div>
              <div className="text-right">
                <div className="text-xs text-text-muted">Upper Bound</div>
                <div className="text-lg font-mono">
                  {result.mhti.confidence_interval.upper.toFixed(3)}
                </div>
              </div>
            </div>
          </div>

          {/* Trend Analysis */}
          {result.trend && result.trend.data_points > 0 && (
            <div className="bg-bg-secondary border border-border rounded-lg p-4">
              <h3 className="text-sm font-bold uppercase text-text-muted mb-3">
                Risk Trend Analysis
              </h3>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <div className="text-xs text-text-muted">Trend (Velocity)</div>
                  <div className="text-xl font-mono flex items-center gap-2">
                    <span className="text-2xl">{getTrendIcon(result.trend.direction)}</span>
                    <span>{result.trend.trend.toFixed(3)}</span>
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Acceleration</div>
                  <div className="text-xl font-mono">{result.trend.acceleration.toFixed(3)}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Direction</div>
                  <div className="text-sm font-bold uppercase">{result.trend.direction}</div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">Confidence</div>
                  <div className="text-sm font-bold uppercase">{result.trend.confidence}</div>
                </div>
              </div>

              {/* Alert */}
              {result.trend.alert && (
                <div
                  className={`p-3 rounded-lg ${
                    result.trend.alert.includes("CRITICAL")
                      ? "bg-accent-danger/20 border border-accent-danger"
                      : result.trend.alert.includes("WARNING")
                      ? "bg-accent-warning/20 border border-accent-warning"
                      : "bg-accent-success/20 border border-accent-success"
                  }`}
                >
                  <p className="text-sm font-medium">{result.trend.alert}</p>
                </div>
              )}

              <div className="text-xs text-text-muted mt-2">
                Based on {result.trend.data_points} historical data points
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
