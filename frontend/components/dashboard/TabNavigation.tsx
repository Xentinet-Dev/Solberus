"use client";

import * as Tabs from "@radix-ui/react-tabs";
import ControlTab from "@/components/tabs/ControlTab";
import StrategiesTab from "@/components/tabs/StrategiesTab";
import SecurityTab from "@/components/tabs/SecurityTab";
import MEVTab from "@/components/tabs/MEVTab";
import MarketMakingTab from "@/components/tabs/MarketMakingTab";
import ArbitrageTab from "@/components/tabs/ArbitrageTab";
import PositionsTab from "@/components/tabs/PositionsTab";
import TradesTab from "@/components/tabs/TradesTab";
import LogsTab from "@/components/tabs/LogsTab";

const tabLabels = [
  "control",
  "strategies",
  "security",
  "mev",
  "market",
  "arbitrage",
  "positions",
  "trades",
  "logs",
];

export default function TabNavigation() {
  return (
    <Tabs.Root defaultValue="control" className="w-full h-full flex flex-col">
      <Tabs.List className="flex px-6 border-b border-border overflow-x-auto scrollbar-hide">
        {tabLabels.map((tab) => (
          <Tabs.Trigger
            key={tab}
            value={tab}
            className="px-4 py-3 text-sm uppercase tracking-wide text-text-secondary hover:text-accent-primary hover:bg-bg-hover data-[state=active]:text-accent-primary data-[state=active]:border-b-2 data-[state=active]:border-accent-primary transition-smooth whitespace-nowrap"
          >
            {tab}
          </Tabs.Trigger>
        ))}
      </Tabs.List>

      <div className="flex-1 overflow-auto">
        <Tabs.Content value="control" className="h-full p-6">
          <ControlTab />
        </Tabs.Content>
        <Tabs.Content value="strategies" className="h-full p-6">
          <StrategiesTab />
        </Tabs.Content>
        <Tabs.Content value="security" className="h-full p-6">
          <SecurityTab />
        </Tabs.Content>
        <Tabs.Content value="mev" className="h-full p-6">
          <MEVTab />
        </Tabs.Content>
        <Tabs.Content value="market" className="h-full p-6">
          <MarketMakingTab />
        </Tabs.Content>
        <Tabs.Content value="arbitrage" className="h-full p-6">
          <ArbitrageTab />
        </Tabs.Content>
        <Tabs.Content value="positions" className="h-full p-6">
          <PositionsTab />
        </Tabs.Content>
        <Tabs.Content value="trades" className="h-full p-6">
          <TradesTab />
        </Tabs.Content>
        <Tabs.Content value="logs" className="h-full p-6">
          <LogsTab />
        </Tabs.Content>
      </div>
    </Tabs.Root>
  );
}

