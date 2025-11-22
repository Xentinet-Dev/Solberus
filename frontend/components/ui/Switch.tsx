"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import { useState } from "react";

interface SwitchProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  defaultChecked?: boolean;
  disabled?: boolean;
}

export function Switch({
  checked,
  onCheckedChange,
  defaultChecked = false,
  disabled = false,
}: SwitchProps) {
  const [internalChecked, setInternalChecked] = useState(defaultChecked);
  const isControlled = checked !== undefined;
  const isChecked = isControlled ? checked : internalChecked;

  const handleCheckedChange = (newChecked: boolean) => {
    if (!isControlled) {
      setInternalChecked(newChecked);
    }
    onCheckedChange?.(newChecked);
  };

  return (
    <SwitchPrimitive.Root
      checked={isChecked}
      onCheckedChange={handleCheckedChange}
      disabled={disabled}
      className="relative inline-flex h-6 w-11 items-center rounded-full bg-bg-secondary border border-border transition-colors focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-primary disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-accent-primary"
    >
      <SwitchPrimitive.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-white transition-transform duration-200 will-change-transform data-[state=checked]:translate-x-[22px]" />
    </SwitchPrimitive.Root>
  );
}

