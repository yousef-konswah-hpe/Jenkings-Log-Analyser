import Image from "next/image";
import { ShieldCheck } from "lucide-react";

type PageHeaderProps = {
  title: string;
  subtitle: string;
};

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <header className="mb-8 overflow-hidden rounded-2xl bg-[linear-gradient(90deg,#003d6b_0%,#0073b8_100%)] p-6 text-white shadow-lg">
      <div className="grid items-center gap-6 md:grid-cols-[1.1fr_0.9fr]">
        <div>
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-8 w-8 text-hpe-green-400" />
            <h1 className="text-3xl font-extrabold tracking-tight text-white md:text-4xl">{title}</h1>
          </div>
          <p className="mt-2 text-sm font-medium text-blue-50/95 md:text-base">{subtitle}</p>
        </div>

        <div className="relative hidden md:block">
          <Image
            src="/images/jenkins-hero.svg"
            alt="AI powered Jenkins dashboard"
            width={760}
            height={360}
            priority
            className="h-auto w-full rounded-xl border border-white/20 shadow-md"
          />
        </div>
      </div>
    </header>
  );
}
