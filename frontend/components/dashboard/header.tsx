"use client";

import { StatusIndicator } from "./status-indicator";
import { WalletInfo } from "./wallet-info";

interface HeaderProps {
  onConnect: () => void;
}

export function Header({ onConnect }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-bg-secondary/80 backdrop-blur-md border-b border-border">
      <div className="container mx-auto px-4 py-4 max-w-7xl">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-accent-primary tracking-wide">
              DOGWIFTOOLS
            </h1>
            <p className="text-xs text-text-secondary">Trading Bot Control Center</p>
          </div>
          
          <div className="flex items-center gap-4">
            <StatusIndicator />
            <WalletInfo onConnect={onConnect} />
          </div>
        </div>
      </div>
    </header>
  );
}

