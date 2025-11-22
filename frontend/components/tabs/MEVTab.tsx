"use client";

import { FormInput } from "@/components/forms/FormInput";
import { FormCheckbox } from "@/components/forms/FormCheckbox";

export default function MEVTab() {
  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">MEV Configuration</h2>
        <p className="text-text-secondary text-sm">
          Configure MEV (Maximal Extractable Value) operations including sandwich attacks and front-running.
        </p>
      </div>

      <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
        <div className="space-y-4">
          <FormInput
            label="Min Profit Threshold (SOL)"
            id="mevMinProfit"
            type="number"
            defaultValue="0.01"
            step="0.001"
            tooltip="Minimum profit required to execute MEV opportunity."
          />
          <FormInput
            label="Min Transaction Size (SOL)"
            id="mevMinTxSize"
            type="number"
            defaultValue="0.1"
            step="0.01"
            tooltip="Minimum transaction size to consider for MEV."
          />
          <FormCheckbox
            label="Enable Sandwich Attacks"
            id="enableSandwich"
            tooltip="Buy just before retail surge, sell immediately after to capture the squeeze."
          />
          <FormCheckbox
            label="Enable Front-Running"
            id="enableFrontRun"
            tooltip="Detect intent signatures and enter one block earlier."
          />
        </div>
        <div className="mt-6 flex gap-4">
          <button className="px-6 py-3 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/90 transition-colors">
            START MEV
          </button>
          <button className="px-6 py-3 bg-accent-danger text-white font-semibold rounded-lg hover:bg-accent-danger/90 transition-colors">
            STOP MEV
          </button>
        </div>
      </div>

      <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
        <h3 className="text-lg font-bold mb-4">MEV Statistics</h3>
        <div className="text-text-muted text-sm">
          Statistics will appear here when MEV bot is running.
        </div>
      </div>
    </div>
  );
}

