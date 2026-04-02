"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle, CalendarClock, Database,
  Loader2, Mail, MailCheck, Upload, Workflow,
} from "lucide-react";
import { toast } from "sonner";

import { Form } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EmptyState } from "@/components/common/empty-state";
import { FormLoadingSkeleton } from "@/components/common/form-loading-skeleton";
import { LogUploadArea } from "@/components/common/log-upload-area";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";
import { useJenkinsJobs } from "@/hooks/use-jenkins-jobs";
import { scheduleEmailReport, emailLogReport } from "@/lib/api";

const scheduleSchema = z.object({
  jobId: z.string().min(1, "Please select a Jenkins job."),
  email: z.string().trim().email("Please enter a valid recipient email."),
  frequency: z.enum(["immediate", "hourly", "daily", "weekly", "monthly"]),
});

type ScheduleFormValues = z.infer<typeof scheduleSchema>;
type TabMode = "job" | "upload";

const frequencyOptions: { label: string; value: ScheduleFormValues["frequency"] }[] = [
  { label: "Send Immediately", value: "immediate" },
  { label: "Hourly", value: "hourly" },
  { label: "Daily", value: "daily" },
  { label: "Weekly", value: "weekly" },
  { label: "Monthly", value: "monthly" },
];

export function ScheduleEmailForm() {
  const { jobs, loading: jobsLoading, error: jobsError } = useJenkinsJobs();

  const [mode, setMode] = useState<TabMode>("job");
  const [apiError, setApiError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [uploadEmail, setUploadEmail] = useState("");
  const [uploading, setUploading] = useState(false);

  const form = useForm<ScheduleFormValues>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: { jobId: "", email: "", frequency: "immediate" },
    mode: "onChange",
  });

  const jobOptions = jobs.map((j) => ({ label: j.display_name, value: j.id }));
  const isSubmitting = form.formState.isSubmitting;
  const busy = isSubmitting || uploading;

  const onSubmitJob = async (values: ScheduleFormValues) => {
    setApiError(""); setSuccessMessage("");
    try {
      const response = await scheduleEmailReport({
        jobId: values.jobId, email: values.email,
        frequency: values.frequency === "immediate" ? undefined : values.frequency,
      });
      setSuccessMessage(response.message); toast.success(response.message); form.reset();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unexpected error.";
      setApiError(msg); toast.error(msg);
    }
  };

  const onSubmitUpload = async () => {
    setApiError(""); setSuccessMessage(""); setUploading(true);
    try {
      if (!uploadEmail.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(uploadEmail.trim())) {
        toast.error("Please enter a valid email address."); return;
      }

      let logContent = "", filename = "pasted_log";
      if (uploadFile) { logContent = await uploadFile.text(); filename = uploadFile.name; }
      else if (pasteText.trim()) { logContent = pasteText.trim(); }
      else { toast.error("Drop a log file or paste log content first."); return; }

      if (logContent.length < 50) { toast.error("Log content too short."); return; }

      const data = await emailLogReport(logContent, uploadEmail.trim(), filename);
      setSuccessMessage(data.message); toast.success(data.message);
      setUploadFile(null); setPasteText(""); setUploadEmail("");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unexpected error.";
      setApiError(msg); toast.error(msg);
    } finally { setUploading(false); }
  };

  const tabClass = (tab: TabMode) =>
    `flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all cursor-pointer ${
      mode === tab
        ? "bg-hpe-green-500 text-white shadow-sm"
        : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
    }`;

  return (
    <div className="space-y-5">
      {/* Mode Tabs */}
      <div className="flex gap-2">
        <button type="button" className={tabClass("job")} onClick={() => setMode("job")}>
          <Workflow className="h-4 w-4" /> From Jenkins Job
        </button>
        <button type="button" className={tabClass("upload")} onClick={() => setMode("upload")}>
          <Upload className="h-4 w-4" /> Upload / Paste Log
        </button>
      </div>

      {/* Job Mode */}
      {mode === "job" && (
        <>
          {jobsError && (
            <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Jobs unavailable</AlertTitle>
              <AlertDescription>{jobsError}</AlertDescription>
            </Alert>
          )}

          {jobsLoading && <FormLoadingSkeleton rows={3} />}

          {!jobsLoading && !jobsError && jobOptions.length === 0 && (
            <EmptyState
              title="No Jenkins jobs found"
              description="You can still continue by typing a Job ID manually below."
              icon={<Database className="h-5 w-5" />}
            />
          )}

          {!jobsLoading && (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmitJob)} className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  {jobOptions.length > 0 ? (
                    <RHFSelectField control={form.control} name="jobId" label="Select Jenkins Job"
                      placeholder="Select a Jenkins job..." options={jobOptions}
                      icon={<Workflow className="h-4 w-4" />} />
                  ) : (
                    <RHFTextField control={form.control} name="jobId" label="Jenkins Job ID"
                      placeholder="Enter job id (for example: 67b2...)"
                      description="No jobs found from API. Enter the backend job ID manually."
                      icon={<Workflow className="h-4 w-4" />} />
                  )}
                </div>
                <div className="md:col-span-2">
                  <RHFTextField control={form.control} name="email" label="Recipient Email"
                    placeholder="user@example.com" type="text" icon={<Mail className="h-4 w-4" />} />
                </div>
                <div className="md:col-span-2">
                  <RHFSelectField control={form.control} name="frequency" label="Frequency"
                    placeholder="Choose frequency" options={frequencyOptions}
                    icon={<CalendarClock className="h-4 w-4" />} />
                </div>
                <div className="md:col-span-2 pt-2">
                  <Button type="submit" disabled={busy || jobsLoading}
                    className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90">
                    {isSubmitting ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Submitting…</>) : "Schedule / Send Email Report"}
                  </Button>
                </div>
              </form>
            </Form>
          )}
        </>
      )}

      {/* Upload / Paste Mode */}
      {mode === "upload" && (
        <div className="space-y-4">
          {/* Email field */}
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-slate-800 dark:text-slate-200">
              Recipient Email
            </label>
            <div className="relative">
              <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-500 dark:text-slate-300">
                <Mail className="h-4 w-4" />
              </span>
              <input
                type="email" placeholder="user@example.com"
                value={uploadEmail} onChange={(e) => setUploadEmail(e.target.value)}
                className="h-11 w-full rounded-md border border-slate-300 bg-white pl-10 pr-4 text-sm text-slate-800 placeholder:text-slate-400 focus:border-hpe-green-500 focus:outline-none focus:ring-1 focus:ring-hpe-green-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
              />
            </div>
          </div>

          <LogUploadArea
            uploadFile={uploadFile} setUploadFile={setUploadFile}
            pasteText={pasteText} setPasteText={setPasteText}
          />

          <Button type="button" onClick={onSubmitUpload}
            disabled={busy || (!uploadFile && !pasteText.trim()) || !uploadEmail.trim()}
            className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90">
            {uploading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Analyzing &amp; Emailing…</>) : "Analyze & Email Report"}
          </Button>
        </div>
      )}

      {/* Errors & Success */}
      {apiError && (
        <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Email request failed</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      {successMessage && (
        <Alert className="border-hpe-green-500/40 bg-white dark:bg-slate-900 dark:border-hpe-green-500/30">
          <MailCheck className="h-4 w-4 text-hpe-green-500" />
          <AlertTitle>Email request submitted</AlertTitle>
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      )}
    </div>
  );
}
