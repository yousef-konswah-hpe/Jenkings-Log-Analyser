import Image from "next/image";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export function TopNav() {
  return (
    <nav className="mb-6 flex items-center justify-between rounded-xl border border-white/15 bg-[linear-gradient(90deg,#0B0F10_0%,#00B388_100%)] px-4 py-3 text-white shadow-lg md:px-5 md:py-4">
      <div className="flex items-center gap-4">
        <div className="rounded-xl bg-white/12 p-2.5 shadow-sm">
          <Image
            src="/images/hpe%20image.jpg"
            alt="HPE logo 1"
            width={56}
            height={56}
            className="h-14 w-14 rounded-md object-cover"
          />
        </div>
        <div>
          <p className="text-base font-semibold tracking-wide md:text-lg">Jenkins Log Analyzer</p>
          <p className="text-sm text-white/90">AI-powered analysis of your latest Jenkins build logs</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden rounded-lg bg-white/12 px-3 py-2 sm:block">
          <Image
            src="/images/hpe1.png"
            alt="HPE logo 2"
            width={120}
            height={42}
            className="h-10 w-auto object-contain"
          />
        </div>
        <ThemeToggle />
      </div>
    </nav>
  );
}
