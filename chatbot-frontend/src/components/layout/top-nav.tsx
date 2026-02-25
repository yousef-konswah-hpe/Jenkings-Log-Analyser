import { Cpu, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export function TopNav() {
  return (
    <nav className="mb-6 flex items-center justify-between rounded-xl border border-white/15 bg-[linear-gradient(90deg,#003d6b_0%,#0073b8_100%)] px-4 py-3 text-white shadow-lg">
      <div className="flex items-center gap-3">
        <div className="rounded-lg bg-white/15 p-2">
          <ShieldCheck className="h-5 w-5 text-hpe-green-400" />
        </div>
        <div>
          <p className="text-sm font-semibold tracking-wide">HPE AI Operations</p>
          <p className="text-xs text-blue-50/90">Jenkins Log Intelligence Console</p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Badge className="hidden border-white/30 bg-white/10 text-white sm:inline-flex">
          <Cpu className="mr-1 h-3.5 w-3.5" />
          Next.js 16 UI
        </Badge>
        <ThemeToggle />
      </div>
    </nav>
  );
}
