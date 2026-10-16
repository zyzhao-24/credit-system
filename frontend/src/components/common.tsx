import type { ReactNode } from "react";

export function EmptyState({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="text-center py-14 text-[#999]">
      <div className="text-5xl mb-4">{icon}</div>
      <div className="text-base">{text}</div>
    </div>
  );
}

export function Field({ label, required, children }: { label: string; required?: boolean; children: ReactNode }) {
  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-[#333] mb-1.5">
        {label} {required ? <span className="text-danger">*</span> : null}
      </label>
      {children}
    </div>
  );
}

export function ProgressBar({ percentage }: { percentage: number }) {
  const width = Math.max(0, Math.min(100, percentage));
  return (
    <div className="relative h-5 w-full rounded-full bg-[#ececec] overflow-hidden">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${width}%` }} />
      <span className="absolute inset-0 flex items-center justify-center text-xs text-[#333]">
        {percentage}%
      </span>
    </div>
  );
}
