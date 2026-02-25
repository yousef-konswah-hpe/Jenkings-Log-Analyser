import { ReactNode } from "react";
import { Footer } from "@/components/layout/footer";
import { SupportChatWidget } from "@/components/support/support-chat-widget";
import { TopNav } from "@/components/layout/top-nav";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-hpe-surface text-slate-900 dark:text-slate-100">
      <main className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-10">
        <TopNav />
        {children}
        <Footer />
      </main>
      <SupportChatWidget />
    </div>
  );
}
