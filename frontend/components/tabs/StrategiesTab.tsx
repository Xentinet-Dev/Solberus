"use client";

import { Switch } from "@/components/ui/Switch";
import Tooltip from "@/components/ui/Tooltip";

const strategies = [
  {
    id: "snipe",
    name: "Sniping",
    desc: "Automated entry on new token launches.",
  },
  {
    id: "volboost",
    name: "Volume Boost",
    desc: "Artificially increases volume presence.",
  },
  {
    id: "marketmake",
    name: "Market Making",
    desc: "Spread-based liquidity provisioning.",
  },
  {
    id: "momentum",
    name: "Momentum",
    desc: "Trend-following algorithmic execution.",
  },
  {
    id: "reversal",
    name: "Reversal",
    desc: "Detects exhaustion points for mean reversion.",
  },
  {
    id: "whalecopy",
    name: "Whale Copy Trading",
    desc: "Mirrors movements of tracked wallets.",
  },
];

export default function StrategiesTab() {
  return (
    <div className="grid grid-cols-3 gap-6">
      {strategies.map((s) => (
        <div
          key={s.id}
          className="bg-bg-tertiary border border-border rounded-lg p-5 hover:shadow-neon transition-smooth"
        >
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold tracking-wide uppercase">{s.name}</h3>
            <Switch />
          </div>
          <p className="text-text-secondary text-sm mt-2">{s.desc}</p>
          <div className="mt-4">
            <Tooltip text={`Details about ${s.name} strategy and recommended use cases.`}>
              <span className="text-accent-primary cursor-pointer">ℹ️ More Info</span>
            </Tooltip>
          </div>
        </div>
      ))}

      {/* Social Signal Intelligence */}
      <div className="col-span-3 bg-bg-tertiary border border-border rounded-lg p-6 mt-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl uppercase font-bold tracking-wide">
            Social Signal Intelligence
          </h2>
          <Switch />
        </div>
        <p className="text-text-secondary text-sm">
          Pulls real-time signals from Twitter, Telegram, Discord, and correlates with
          token movement.
        </p>
      </div>
    </div>
  );
}

