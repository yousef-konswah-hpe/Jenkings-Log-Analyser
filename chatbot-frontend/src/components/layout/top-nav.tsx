import Image from "next/image";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export function TopNav() {
  return (
    <nav className="mb-6 flex items-center justify-between rounded-xl border border-white/15 bg-[linear-gradient(90deg,#0B0F10_0%,#00B388_100%)] px-4 py-3 text-white shadow-lg md:px-5 md:py-4">
      <div className="flex items-center gap-4">
        <div className="rounded-xl bg-white/12 p-2 shadow-sm">
          <Image
            src="/images/hpe%20image.jpg"
            alt="HPE logo 1"
            width={44}
            height={44}
            className="h-11 w-11 rounded-md object-cover"
          />
        </div>
        <div>
          <p className="text-base font-semibold tracking-wide md:text-lg">HPE AI Operations</p>
          <p className="text-sm text-white/90">Jenkins Log Intelligence Console</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden rounded-lg bg-white/12 px-2 py-1.5 sm:block">
          <Image
            src="/images/hpe1.png"
            alt="HPE logo 2"
            width={88}
            height={30}
            className="h-7 w-auto object-contain"
          />
        </div>
        <ThemeToggle />
      </div>
    </nav>
  );
}
