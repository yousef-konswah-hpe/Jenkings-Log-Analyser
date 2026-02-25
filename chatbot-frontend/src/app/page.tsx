import { SectionCard } from "@/components/common/section-card";
import { AppShell } from "@/components/layout/app-shell";
import { PageHeader } from "@/components/layout/page-header";
import { Separator } from "@/components/ui/separator";

export default function Home() {
  return (
    <AppShell>
      <PageHeader
        title="Jenkins Log Analyzer"
        subtitle="AI-powered analysis with clean, reusable HPE-themed UI."
      />

      <div className="grid gap-6">
        <SectionCard
          title="Analyze Jenkins Build"
          description="Reusable section for Jenkins job input and analysis action."
        >
          <p className="text-sm text-slate-600">
            Next step: wire full form with zod + react-hook-form.
          </p>
        </SectionCard>

        <Separator />

        <SectionCard
          title="Schedule Email Report"
          description="Reusable section for recipient and schedule controls."
        >
          <p className="text-sm text-slate-600">
            Next step: build validated scheduling form and API integration.
          </p>
        </SectionCard>
      </div>
    </AppShell>
  );
}
