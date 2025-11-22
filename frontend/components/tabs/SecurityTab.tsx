"use client";

import Tooltip from "@/components/ui/Tooltip";
import { Button } from "@/components/ui/Button";

export default function SecurityTab() {
  return (
    <div className="space-y-6">
      <div className="bg-bg-tertiary border border-border p-6 rounded-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold uppercase tracking-wide">Security Scan</h2>
          <Button variant="primary">Run Scan</Button>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {/* Honeypot Check */}
          <div className="p-4 bg-bg-secondary border border-border rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary uppercase">Honeypot Check</span>
              <Tooltip text="Detects if a token prevents sells or manipulates liquidity." />
            </div>
            <div className="mt-2 text-accent-success font-bold">SAFE</div>
          </div>

          {/* Mint Authority */}
          <div className="p-4 bg-bg-secondary border border-border rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary uppercase">Mint Authority</span>
              <Tooltip text="Checks if token mint authority is revoked." />
            </div>
            <div className="mt-2 text-accent-danger font-bold">RISK</div>
          </div>

          {/* Freeze Authority */}
          <div className="p-4 bg-bg-secondary border border-border rounded-lg">
            <div className="flex items-center justify-between">
              <span className="text-sm text-text-secondary uppercase">Freeze Authority</span>
              <Tooltip text="Detects if tokens can be frozen or restricted." />
            </div>
            <div className="mt-2 text-accent-warning font-bold">WARNING</div>
          </div>
        </div>
      </div>

      {/* Security settings */}
      <div className="bg-bg-tertiary border border-border p-6 rounded-lg">
        <h3 className="text-lg font-bold uppercase tracking-wide mb-4">Security Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-sm uppercase text-text-muted block mb-2">
              Auto-Sell Dangerous Tokens
            </label>
            <select className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-text-primary focus:outline-none focus:border-accent-primary">
              <option>Enabled</option>
              <option>Disabled</option>
            </select>
          </div>
          <div>
            <label className="text-sm uppercase text-text-muted block mb-2">
              Blacklist On Detection
            </label>
            <select className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-text-primary focus:outline-none focus:border-accent-primary">
              <option>Enabled</option>
              <option>Disabled</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}

