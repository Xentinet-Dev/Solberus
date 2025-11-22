"use client";

import { Tooltip } from "@/components/ui/Tooltip";

interface Option {
  value: string;
  label: string;
}

interface FormSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  tooltip?: string;
  options: Option[];
}

export function FormSelect({
  label,
  tooltip,
  id,
  options,
  ...props
}: FormSelectProps) {
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
      <select
        id={id}
        className="w-full px-4 py-2 bg-bg-secondary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-colors"
        {...props}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

