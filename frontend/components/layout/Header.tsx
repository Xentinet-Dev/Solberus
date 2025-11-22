"use client";

import StatusIndicator from "@/components/ui/StatusIndicator";
import { useAppStore } from "@/store/app-store";

export default function Header() {
  const wallet = useAppStore((state) => state.wallet);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-md bg-bg-secondary/60 border-b border-border">
      <div className="flex items-center justify-between px-6 h-16">
        <div className="text-xl font-bold tracking-wide text-accent-primary">
          DOGWIFTOOLS
        </div>
        <div className="flex items-center gap-4">
          <StatusIndicator />
          {wallet && (
            <div className="text-sm text-text-secondary font-mono">
              {wallet.slice(0, 8)}...{wallet.slice(-8)}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

