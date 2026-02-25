import { ShieldCheck } from "lucide-react";

type PageHeaderProps = {
  title: string;
  subtitle: string;
};

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <header className="mb-8 rounded-2xl bg-[linear-gradient(90deg,#003d6b_0%,#0073b8_100%)] p-6 text-white shadow-lg">
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-8 w-8 text-hpe-green-400" />
        <h1 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">{title}</h1>
      </div>
      <p className="mt-2 text-sm font-medium text-blue-50/95 md:text-base">{subtitle}</p>
    </header>
  );
}
