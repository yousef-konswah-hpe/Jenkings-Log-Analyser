"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle, Database, KeyRound, Link2,
  Loader2, Upload, UserRound, Workflow,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AnalysisResultCard } from "@/components/common/analysis-result-card";
import { EmptyState } from "@/components/common/empty-state";
import { FormLoadingSkeleton } from "@/components/common/form-loading-skeleton";
import { LogUploadArea } from "@/components/common/log-upload-area";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";
import { useJenkinsJobs } from "@/hooks/use-jenkins-jobs";
import { analyzeJenkinsBuild, analyzeLogText } from "@/lib/api";

const analyzeSchema = z.object({
  jobId: z.string().min(1, "Please select a Jenkins job."),
  jenkinsUrl: z.string().trim().optional()
    .refine((v) => !v || /^https?:\/\/.+/i.test(v), "Enter a valid URL starting with http:// or https://."),
  username: z.string().trim().optional(),
  password: z.string().trim().optional(),
});

type AnalyzeFormValues = z.infer<typeof analyzeSchema>;
type AnalysisResult = { response: string; jobName?: string; buildNumber?: number | string };
type TabMode = "job" | "upload";

export function AnalyzeJenkinsForm() {
  const { jobs, loading: jobsLoading, error: jobsError } = useJenkinsJobs();

  const [mode, setMode] = useState<TabMode>("job");
  const [apiError, setApiError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  // Upload state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [uploading, setUploading] = useState(false);

  const form = useForm<AnalyzeFormValues>({
    resolver: zodResolver(analyzeSchema),
    defaultValues: { jobId: "", jenkinsUrl: "", username: "", password: "" },
    mode: "onChange",
  });

  const isSubmitting = form.formState.isSubmitting;
  const busy = isSubmitting || uploading;
  const jobOptions = jobs.map((j) => ({ label: j.display_name, value: j.id }));

  const onSubmitJob = async (values: AnalyzeFormValues) => {
    setApiError(""); setResult(null);
    try {
      const data = await analyzeJenkinsBuild({
        job_id: values.jobId,
        jenkins_url: values.jenkinsUrl?.trim() || undefined,
        username: values.username?.trim() || undefined,
        password: values.password?.trim() || undefined,
      });
      setResult({ response: data.response ?? "No analysis text returned.", jobName: data.job_name, buildNumber: data.build_number });
      toast.success("Analysis completed successfully.");
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Unexpected error.";
      setApiError(msg); toast.error(msg);
    }
  };

  const onSubmitUpload = async () => {
    setApiError(""); setResult(null); setUploading(true);
    try {
      let logContent = "", filename = "pasted_log";
      if (uploadFile) { logContent = await uploadFile.text(); filename = uploadFile.name; }
      else if (pasteText.trim()) { logContent = pasteText.trim(); }
      else { toast.error("Drop a log file or paste log content first."); return; }

      if (logContent.length < 50) { toast.error("Log content too short."); return; }

      const data = await analyzeLogText(logContent, filename);
      setResult({ response: data.response ?? "No analysis text returned.", jobName: data.job_name, buildNumber: data.build_number });
      toast.success("Log analysis completed successfully.");
      setUploadFile(null); setPasteText("");
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
          <Workflow className="h-4 w-4" /> Analyze from Jenkins
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

          {jobsLoading && <FormLoadingSkeleton rows={4} />}

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
                      description="Required. Choose the Jenkins job to analyze."
                      icon={<Workflow className="h-4 w-4" />} />
                  ) : (
                    <RHFTextField control={form.control} name="jobId" label="Jenkins Job ID"
                      placeholder="Enter job id (for example: 67b2...)"
                      description="No jobs found from API. Enter the backend job ID manually."
                      icon={<Workflow className="h-4 w-4" />} />
                  )}
                </div>
                <div className="md:col-span-2">
                  <RHFTextField control={form.control} name="jenkinsUrl" label="Jenkins URL"
                    placeholder="https://jenkins.example.com" type="url"
                    icon={<Link2 className="h-4 w-4" />} />
                </div>
                <RHFTextField control={form.control} name="username" label="Jenkins Username"
                  placeholder="your-jenkins-username" icon={<UserRound className="h-4 w-4" />} />
                <RHFTextField control={form.control} name="password" label="Jenkins Password / API Token"
                  placeholder="your-password-or-api-token" type="password"
                  icon={<KeyRound className="h-4 w-4" />} />
                <div className="md:col-span-2 pt-2">
                  <Button type="submit" disabled={busy || jobsLoading}
                    className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90">
                    {isSubmitting ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Analyzing Latest Build…</>) : "Analyze Latest Jenkins Build"}
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
          <LogUploadArea
            uploadFile={uploadFile} setUploadFile={setUploadFile}
            pasteText={pasteText} setPasteText={setPasteText}
          />
          <Button type="button" onClick={onSubmitUpload}
            disabled={busy || (!uploadFile && !pasteText.trim())}
            className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90">
            {uploading ? (<><Loader2 className="mr-2 h-4 w-4 animate-spin" />Analyzing Log…</>) : "Analyze Uploaded Log"}
          </Button>
        </div>
      )}

      {/* Errors & Result */}
      {apiError && (
        <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Analysis failed</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      )}

      {result && (
        <AnalysisResultCard response={result.response} jobName={result.jobName} buildNumber={result.buildNumber} />
      )}
    </div>
  );
}
