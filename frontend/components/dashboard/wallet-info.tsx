"use client";

interface WalletInfoProps {
  onConnect: () => void;
}

export function WalletInfo({ onConnect }: WalletInfoProps) {
  // TODO: Get from Zustand store
  const walletAddress = null;

  if (!walletAddress) {
    return (
      <button
        onClick={onConnect}
        className="px-4 py-2 bg-accent-primary text-black font-semibold rounded-lg hover:bg-accent-primary/90 transition-colors"
      >
        Connect Wallet
      </button>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-text-secondary font-mono">
        {walletAddress.slice(0, 8)}...{walletAddress.slice(-8)}
      </span>
      <button className="px-3 py-1.5 text-sm bg-bg-tertiary border border-border rounded hover:bg-bg-hover transition-colors">
        Disconnect
      </button>
    </div>
  );
}

