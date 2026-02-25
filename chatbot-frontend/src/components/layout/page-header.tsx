import { ShieldCheck } from "lucide-react";

type PageHeaderProps = {
  title: string;
  subtitle: string;
};

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <header className="mb-8 rounded-2xl bg-gradient-to-r from-hpe-blue-900 to-hpe-blue-700 p-6 text-white shadow-lg">
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-8 w-8 text-hpe-green-400" />
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
      </div>
      <p className="mt-2 text-sm text-blue-100 md:text-base">{subtitle}</p>
    </header>
  );
}
