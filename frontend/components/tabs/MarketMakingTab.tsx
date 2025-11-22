"use client";

import { FormInput } from "@/components/forms/FormInput";
import { FormSelect } from "@/components/forms/FormSelect";

export default function MarketMakingTab() {
  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">Market Making Configuration</h2>
        <p className="text-text-secondary text-sm">
          Configure automated market making to provide liquidity with spread.
        </p>
      </div>

      <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
        <div className="space-y-4">
          <FormInput
            label="Token Mint Address"
            id="mmTokenMint"
            placeholder="Token mint address"
            tooltip="The token mint address to provide market making for."
          />
          <FormSelect
            label="Platform"
            id="mmPlatform"
            options={[
              { value: "pump_fun", label: "Pump.fun" },
              { value: "lets_bonk", label: "LetsBonk" },
            ]}
            tooltip="Select the platform for market making."
          />
          <FormInput
            label="Target SOL Ratio (0.0-1.0)"
            id="mmTargetSolRatio"
            type="number"
            defaultValue="0.5"
            step="0.1"
            min="0"
            max="1"
            tooltip="Target ratio of SOL to tokens in the market making position."
          />
          <FormInput
            label="Spread (%)"
            id="mmSpread"
            type="number"
            defaultValue="2"
            step="0.1"
            tooltip="Bid-ask spread percentage for market making."
          />
        </div>
        <div className="mt-6 flex gap-4">
          <button className="px-6 py-3 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/90 transition-colors">
            START MARKET MAKING
          </button>
          <button className="px-6 py-3 bg-accent-danger text-white font-semibold rounded-lg hover:bg-accent-danger/90 transition-colors">
            STOP MARKET MAKING
          </button>
        </div>
      </div>
    </div>
  );
}

