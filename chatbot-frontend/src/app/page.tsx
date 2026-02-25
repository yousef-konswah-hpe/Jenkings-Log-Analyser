import { SectionCard } from "@/components/common/section-card";
import { AnalyzeJenkinsForm } from "@/components/forms/analyze-jenkins-form";
import { ScheduleEmailForm } from "@/components/forms/schedule-email-form";
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
          description="Validated input powered by Zod + react-hook-form."
        >
          <AnalyzeJenkinsForm />
        </SectionCard>

        <Separator />

        <SectionCard
          title="Schedule Email Report"
          description="Send immediately or schedule recurring report emails with validation."
        >
          <ScheduleEmailForm />
        </SectionCard>
      </div>
    </AppShell>
  );
}
