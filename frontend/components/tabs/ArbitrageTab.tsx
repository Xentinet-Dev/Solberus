"use client";

import { FormInput } from "@/components/forms/FormInput";

export default function ArbitrageTab() {
  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">Arbitrage Configuration</h2>
        <p className="text-text-secondary text-sm">
          Configure arbitrage bot to capture price differences across platforms.
        </p>
      </div>

      <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
        <div className="space-y-4">
          <FormInput
            label="Min Profit Percentage (%)"
            id="arbMinProfit"
            type="number"
            defaultValue="2"
            step="0.1"
            tooltip="Minimum profit percentage required to execute arbitrage."
          />
          <FormInput
            label="Min Profit (SOL)"
            id="arbMinProfitSol"
            type="number"
            defaultValue="0.01"
            step="0.001"
            tooltip="Minimum profit in SOL required to execute arbitrage."
          />
        </div>
        <div className="mt-6 flex gap-4">
          <button className="px-6 py-3 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/90 transition-colors">
            START ARBITRAGE
          </button>
          <button className="px-6 py-3 bg-accent-danger text-white font-semibold rounded-lg hover:bg-accent-danger/90 transition-colors">
            STOP ARBITRAGE
          </button>
        </div>
      </div>
    </div>
  );
}

