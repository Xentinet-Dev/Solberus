"use client";

import { useState } from "react";
import { Header } from "./header";
import { StatCards } from "./stat-cards";
import { TabNavigation } from "./tab-navigation";
import { ControlTab } from "./tabs/control-tab";
import { StrategiesTab } from "./tabs/strategies-tab";
import { SecurityTab } from "./tabs/security-tab";
import { MEVTab } from "./tabs/mev-tab";
import { MarketMakingTab } from "./tabs/market-making-tab";
import { ArbitrageTab } from "./tabs/arbitrage-tab";
import { PositionsTab } from "./tabs/positions-tab";
import { TradesTab } from "./tabs/trades-tab";
import { LogsTab } from "./tabs/logs-tab";
import { WalletConnectModal } from "./wallet-connect-modal";

type Tab = 
  | "control" 
  | "strategies" 
  | "security" 
  | "mev" 
  | "market-making" 
  | "arbitrage" 
  | "positions" 
  | "trades" 
  | "logs";

export function Dashboard() {
  const [activeTab, setActiveTab] = useState<Tab>("control");
  const [showWalletModal, setShowWalletModal] = useState(false);

  return (
    <div className="min-h-screen bg-bg-primary">
      <Header onConnect={() => setShowWalletModal(true)} />
      
      <main className="container mx-auto px-4 py-8 max-w-7xl">
        <StatCards />
        
        <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
        
        <div className="mt-6">
          {activeTab === "control" && <ControlTab />}
          {activeTab === "strategies" && <StrategiesTab />}
          {activeTab === "security" && <SecurityTab />}
          {activeTab === "mev" && <MEVTab />}
          {activeTab === "market-making" && <MarketMakingTab />}
          {activeTab === "arbitrage" && <ArbitrageTab />}
          {activeTab === "positions" && <PositionsTab />}
          {activeTab === "trades" && <TradesTab />}
          {activeTab === "logs" && <LogsTab />}
        </div>
      </main>

      {showWalletModal && (
        <WalletConnectModal onClose={() => setShowWalletModal(false)} />
      )}
    </div>
  );
}

