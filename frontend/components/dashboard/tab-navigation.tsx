"use client";

import * as Tabs from "@radix-ui/react-tabs";

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

interface TabNavigationProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
}

const tabs: { id: Tab; label: string }[] = [
  { id: "control", label: "CONTROL" },
  { id: "strategies", label: "STRATEGIES" },
  { id: "security", label: "SECURITY" },
  { id: "mev", label: "MEV" },
  { id: "market-making", label: "MARKET MAKING" },
  { id: "arbitrage", label: "ARBITRAGE" },
  { id: "positions", label: "POSITIONS" },
  { id: "trades", label: "TRADES" },
  { id: "logs", label: "LOGS" },
];

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  return (
    <Tabs.Root value={activeTab} onValueChange={(v) => onTabChange(v as Tab)}>
      <Tabs.List className="flex gap-2 border-b border-border overflow-x-auto scrollbar-hide">
        {tabs.map((tab) => (
          <Tabs.Trigger
            key={tab.id}
            value={tab.id}
            className="px-6 py-3 text-sm font-semibold uppercase tracking-wide text-text-secondary border-b-2 border-transparent hover:text-accent-primary transition-colors data-[state=active]:text-accent-primary data-[state=active]:border-accent-primary"
          >
            {tab.label}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
    </Tabs.Root>
  );
}

