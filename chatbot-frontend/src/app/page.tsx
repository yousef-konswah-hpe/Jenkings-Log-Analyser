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
        subtitle="AI-powered analysis of your latest Jenkins build logs"
      />

      <div className="grid gap-6">
        <SectionCard
          title="Analyze Jenkins Build"
          description="Select a Jenkins job or upload a log file to analyze."
        >
          <AnalyzeJenkinsForm />
        </SectionCard>

        <Separator />

        <SectionCard
          title="Schedule Email Report"
          description="Email analysis reports from a Jenkins job or an uploaded log file."
        >
          <ScheduleEmailForm />
        </SectionCard>
      </div>
    </AppShell>
  );
}
