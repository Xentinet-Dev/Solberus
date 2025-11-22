"use client";

import * as Dialog from "@radix-ui/react-dialog";

interface WalletConnectModalProps {
  onClose: () => void;
}

export function WalletConnectModal({ onClose }: WalletConnectModalProps) {
  return (
    <Dialog.Root open={true} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-bg-tertiary border border-border rounded-lg p-6 w-full max-w-md z-50">
          <Dialog.Title className="text-xl font-bold mb-2">
            Connect Wallet
          </Dialog.Title>
          <Dialog.Description className="text-sm text-text-secondary mb-6">
            Select your wallet to connect
          </Dialog.Description>
          
          <div className="space-y-3">
            {/* TODO: Implement wallet detection and connection */}
            <button className="w-full p-4 bg-bg-secondary border border-border rounded-lg hover:border-accent-primary transition-colors text-left">
              <div className="flex items-center gap-3">
                <span className="text-2xl">👻</span>
                <div>
                  <div className="font-semibold">Phantom</div>
                  <div className="text-xs text-text-muted">Solana wallet</div>
                </div>
              </div>
            </button>
          </div>
          
          <Dialog.Close asChild>
            <button className="mt-6 w-full px-4 py-2 bg-bg-secondary border border-border rounded hover:bg-bg-hover transition-colors">
              Cancel
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

