import { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description: string;
  icon?: ReactNode;
};

export function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center dark:border-slate-700 dark:bg-slate-900/60">
      {icon ? <div className="mb-3 flex justify-center text-slate-500 dark:text-slate-300">{icon}</div> : null}
      <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">{title}</h3>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{description}</p>
    </div>
  );
}
