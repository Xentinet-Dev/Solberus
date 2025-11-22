"use client";

import { Tooltip } from "@/components/ui/Tooltip";

interface FormCheckboxProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  tooltip?: string;
}

export function FormCheckbox({
  label,
  tooltip,
  id,
  ...props
}: FormCheckboxProps) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="checkbox"
        id={id}
        className="w-4 h-4 rounded border-border bg-bg-secondary text-accent-primary focus:ring-accent-primary focus:ring-2"
        {...props}
      />
      <label htmlFor={id} className="flex items-center gap-2 text-sm font-medium cursor-pointer">
        {label}
        {tooltip && (
          <Tooltip content={tooltip}>
            <span className="w-4 h-4 rounded-full bg-accent-primary/15 text-accent-primary text-xs flex items-center justify-center cursor-help hover:bg-accent-primary/25 transition-colors">
              ℹ️
            </span>
          </Tooltip>
        )}
      </label>
    </div>
  );
}

