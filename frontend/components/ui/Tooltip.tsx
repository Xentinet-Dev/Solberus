"use client";

import * as RadixTooltip from "@radix-ui/react-tooltip";

interface TooltipProps {
  text: string;
  children?: React.ReactNode;
}

export default function Tooltip({ text, children }: TooltipProps) {
  return (
    <RadixTooltip.Provider delayDuration={150}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>
          {children ? (
            children
          ) : (
            <span className="cursor-pointer text-accent-primary">ℹ️</span>
          )}
        </RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content
            side="top"
            className="max-w-[320px] p-3 bg-bg-secondary text-text-secondary rounded-md border border-border backdrop-blur-md shadow-neon animate-in fade-in-0 zoom-in-95 z-50"
            sideOffset={8}
          >
            {text}
            <RadixTooltip.Arrow className="fill-bg-secondary" />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  );
}

