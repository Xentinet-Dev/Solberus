"use client";

import { useState } from "react";
import { Tooltip } from "@/components/ui/Tooltip";
import { FormInput } from "@/components/forms/FormInput";
import { FormSelect } from "@/components/forms/FormSelect";
import { FormCheckbox } from "@/components/forms/FormCheckbox";

export default function ControlTab() {
  const [listenerType, setListenerType] = useState("logs");
  const [exitStrategy, setExitStrategy] = useState("time_based");

  return (
    <div className="space-y-6">
      <div className="mb-6">
        <h2 className="text-xl font-bold mb-2">Bot Control</h2>
        <p className="text-text-secondary text-sm">
          Configure your trading bot with precision. Settings are organized into focused sections for optimal workflow efficiency.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection Section */}
        <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
          <h3 className="text-lg font-bold mb-4 text-accent-primary">Connection</h3>
          <div className="space-y-4">
            <FormInput
              label="RPC Endpoint"
              id="rpcEndpoint"
              placeholder="https://mainnet.helius-rpc.com/?api-key=..."
              tooltip="Your Solana RPC endpoint for blockchain queries. Use a dedicated RPC provider (Helius, QuickNode, etc.) for optimal performance."
            />
            <FormInput
              label="WSS Endpoint"
              id="wssEndpoint"
              placeholder="wss://mainnet.helius-rpc.com/?api-key=..."
              tooltip="WebSocket endpoint for real-time blockchain data streaming. Must match your RPC provider."
            />
            <FormSelect
              label="Platform"
              id="platform"
              options={[
                { value: "pump_fun", label: "Pump.fun" },
                { value: "lets_bonk", label: "LetsBonk" },
              ]}
              tooltip="Select the token launch platform. Pump.fun is the primary platform with high volume."
            />
            <FormSelect
              label="Listener Type"
              id="listenerType"
              value={listenerType}
              onChange={(e) => setListenerType(e.target.value)}
              options={[
                { value: "logs", label: "Logs (Recommended)" },
                { value: "blocks", label: "Blocks" },
                { value: "geyser", label: "Geyser (Fastest)" },
                { value: "pumpportal", label: "PumpPortal" },
              ]}
              tooltip="Token detection method. Logs: Most compatible. Geyser: Fastest, requires Yellowstone gRPC."
            />
            {listenerType === "geyser" && (
              <>
                <FormInput
                  label="Geyser Endpoint"
                  id="geyserEndpoint"
                  placeholder="wss://your-geyser-endpoint.com"
                  tooltip="Yellowstone gRPC endpoint for Geyser listener."
                />
                <FormInput
                  label="Geyser API Token"
                  id="geyserToken"
                  placeholder="Your Geyser API token"
                  tooltip="Authentication token for Geyser endpoint."
                />
              </>
            )}
            {listenerType === "pumpportal" && (
              <FormInput
                label="PumpPortal URL"
                id="pumpportalUrl"
                defaultValue="wss://pumpportal.fun/api/data"
                tooltip="PumpPortal WebSocket URL for enhanced token data."
              />
            )}
          </div>
        </div>

        {/* Trading Section */}
        <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
          <h3 className="text-lg font-bold mb-4 text-accent-primary">Trading</h3>
          <div className="space-y-4">
            <FormInput
              label="Buy Amount (SOL)"
              id="buyAmount"
              type="number"
              defaultValue="0.01"
              step="0.001"
              tooltip="Capital allocation per trade. Start conservative (0.01-0.1 SOL) for testing."
            />
            <FormInput
              label="Buy Slippage (%)"
              id="buySlippage"
              type="number"
              defaultValue="30"
              tooltip="Maximum acceptable price deviation when buying. Higher slippage increases fill probability."
            />
            <FormInput
              label="Sell Slippage (%)"
              id="sellSlippage"
              type="number"
              defaultValue="30"
              tooltip="Maximum acceptable price deviation when selling."
            />
            <FormSelect
              label="Exit Strategy"
              id="exitStrategy"
              value={exitStrategy}
              onChange={(e) => setExitStrategy(e.target.value)}
              options={[
                { value: "time_based", label: "Time-Based" },
                { value: "tp_sl", label: "Take Profit / Stop Loss" },
                { value: "manual", label: "Manual" },
              ]}
              tooltip="Position exit methodology. Time-Based: Hold for fixed duration. TP/SL: Take profit and stop loss thresholds."
            />
            {exitStrategy === "time_based" && (
              <FormInput
                label="Max Hold Time (seconds)"
                id="maxHoldTime"
                type="number"
                defaultValue="300"
                tooltip="Maximum duration to hold a position before automatic exit."
              />
            )}
            {exitStrategy === "tp_sl" && (
              <div className="grid grid-cols-2 gap-4">
                <FormInput
                  label="Take Profit (%)"
                  id="takeProfit"
                  type="number"
                  defaultValue="50"
                  tooltip="Profit target percentage. When position reaches this gain, automatically sell."
                />
                <FormInput
                  label="Stop Loss (%)"
                  id="stopLoss"
                  type="number"
                  defaultValue="20"
                  tooltip="Maximum acceptable loss percentage. Triggers automatic exit to limit downside."
                />
              </div>
            )}
            <FormInput
              label="Price Check Interval (seconds)"
              id="priceCheckInterval"
              type="number"
              defaultValue="10"
              tooltip="Frequency of position price evaluation."
            />
            <FormInput
              label="Max Token Age (seconds)"
              id="maxTokenAge"
              type="number"
              defaultValue="0.001"
              step="0.001"
              tooltip="Maximum age of tokens to consider for trading."
            />
          </div>
        </div>
      </div>

      {/* Advanced Section */}
      <div className="bg-bg-tertiary p-6 border border-border rounded-lg">
        <h3 className="text-lg font-bold mb-4 text-accent-primary">Advanced</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
              Priority Fees
            </h4>
            <FormCheckbox
              label="Enable Dynamic Priority Fee"
              id="enableDynamicFee"
              tooltip="Automatically adjust priority fees based on network congestion."
            />
            <FormCheckbox
              label="Enable Fixed Priority Fee"
              id="enableFixedFee"
              defaultChecked
              tooltip="Use a constant priority fee for all transactions."
            />
            <FormInput
              label="Fixed Priority Fee (lamports)"
              id="fixedPriorityFee"
              type="number"
              defaultValue="200000"
              tooltip="Base priority fee in lamports. Typical range: 50,000-500,000."
            />
            <FormInput
              label="Extra Priority Fee (%)"
              id="extraPriorityFee"
              type="number"
              defaultValue="0"
              step="0.1"
              tooltip="Additional percentage multiplier applied to base fee during high-competition periods."
            />
            <FormInput
              label="Hard Cap (lamports)"
              id="hardCapFee"
              type="number"
              defaultValue="200000"
              tooltip="Maximum priority fee ceiling to prevent excessive costs."
            />
          </div>
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-text-secondary uppercase tracking-wide">
              Trading Filters
            </h4>
            <FormInput
              label="Match String"
              id="matchString"
              placeholder="Optional: e.g., 'PEPE', 'BONK'"
              tooltip="Filter tokens by name or symbol pattern."
            />
            <FormInput
              label="Bro Address (Copy Trading)"
              id="broAddress"
              placeholder="Optional: Wallet address to copy"
              tooltip="Mirror trades from a specific wallet address."
            />
            <FormCheckbox
              label="Marry Mode"
              id="marryMode"
              tooltip="Hold positions until token migration to Raydium."
            />
            <FormCheckbox
              label="YOLO Mode"
              id="yoloMode"
              tooltip="Disables all safety filters. Use with extreme caution."
            />
            <h4 className="text-sm font-semibold text-text-secondary uppercase tracking-wide mt-6">
              Advanced Configuration
            </h4>
            <FormInput
              label="Max Retries"
              id="maxRetries"
              type="number"
              defaultValue="3"
              tooltip="Maximum transaction retry attempts on failure."
            />
            <FormInput
              label="Wait After Creation (seconds)"
              id="waitAfterCreation"
              type="number"
              defaultValue="15"
              tooltip="Delay after detecting new token before attempting trade."
            />
            <FormInput
              label="Wait After Buy (seconds)"
              id="waitAfterBuy"
              type="number"
              defaultValue="15"
              tooltip="Cooldown period after successful purchase."
            />
          </div>
        </div>
      </div>

      <div className="flex gap-4">
        <button className="px-6 py-3 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/90 transition-colors">
          START BOT
        </button>
        <button className="px-6 py-3 bg-accent-danger text-white font-semibold rounded-lg hover:bg-accent-danger/90 transition-colors">
          STOP BOT
        </button>
      </div>
    </div>
  );
}

