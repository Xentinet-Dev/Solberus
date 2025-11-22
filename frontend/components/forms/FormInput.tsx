"use client";

import { Tooltip } from "@/components/ui/Tooltip";

interface FormInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  tooltip?: string;
}

export function FormInput({ label, tooltip, id, ...props }: FormInputProps) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium">
        {label}
        {tooltip && (
          <Tooltip content={tooltip}>
            <span className="w-4 h-4 rounded-full bg-accent-primary/15 text-accent-primary text-xs flex items-center justify-center cursor-help hover:bg-accent-primary/25 transition-colors">
              ℹ️
            </span>
          </Tooltip>
        )}
      </label>
      <input
        id={id}
        className="w-full px-4 py-2 bg-bg-secondary border border-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors"
        {...props}
      />
    </div>
  );
}

