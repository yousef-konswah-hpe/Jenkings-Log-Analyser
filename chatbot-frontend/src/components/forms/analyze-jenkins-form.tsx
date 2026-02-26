"use client";

import { useCallback, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle,
  Database,
  FileText,
  KeyRound,
  Link2,
  Loader2,
  Upload,
  UserRound,
  Workflow,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AnalysisResultCard } from "@/components/common/analysis-result-card";
import { EmptyState } from "@/components/common/empty-state";
import { FormLoadingSkeleton } from "@/components/common/form-loading-skeleton";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";
import { useJenkinsJobs } from "@/hooks/use-jenkins-jobs";
import { analyzeJenkinsBuild, analyzeLogText } from "@/lib/api";

/* ── Schemas ── */
const analyzeSchema = z.object({
  jobId: z.string().min(1, "Please select a Jenkins job."),
  jenkinsUrl: z
    .string()
    .trim()
    .optional()
    .refine(
      (v) => !v || /^https?:\/\/.+/i.test(v),
      "Please enter a valid URL starting with http:// or https://."
    ),
  username: z.string().trim().optional(),
  password: z.string().trim().optional(),
});

type AnalyzeFormValues = z.infer<typeof analyzeSchema>;

type AnalysisResult = {
  response: string;
  jobName?: string;
  buildNumber?: number | string;
};

type TabMode = "job" | "upload";

const ACCEPTED_EXTENSIONS = [".txt", ".log", ".out", ".console"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

/* ── Component ── */
export function AnalyzeJenkinsForm() {
  const { jobs, loading: jobsLoading, error: jobsError } = useJenkinsJobs();

  const [mode, setMode] = useState<TabMode>("job");
  const [apiError, setApiError] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);

  /* upload state */
  const [dragOver, setDragOver] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* job form */
  const form = useForm<AnalyzeFormValues>({
    resolver: zodResolver(analyzeSchema),
    defaultValues: { jobId: "", jenkinsUrl: "", username: "", password: "" },
    mode: "onChange",
  });

  const isSubmitting = form.formState.isSubmitting;

  const jobOptions = jobs.map((j) => ({ label: j.display_name, value: j.id }));

  /* ── Job-based submit ── */
  const onSubmitJob = async (values: AnalyzeFormValues) => {
    setApiError("");
    setResult(null);
    try {
      const data = await analyzeJenkinsBuild({
        job_id: values.jobId,
        jenkins_url: values.jenkinsUrl?.trim() || undefined,
        username: values.username?.trim() || undefined,
        password: values.password?.trim() || undefined,
      });
      setResult({
        response: data.response ?? "No analysis text returned.",
        jobName: data.job_name,
        buildNumber: data.build_number,
      });
      toast.success("Analysis completed successfully.");
      form.reset();
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Unexpected error while calling analysis API.";
      setApiError(msg);
      toast.error(msg);
    }
  };

  /* ── File helpers ── */
  const validateFile = (file: File): string | null => {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return `Unsupported file type "${ext}". Use ${ACCEPTED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max is 20 MB.`;
    }
    return null;
  };

  const handleFileSelect = useCallback((file: File) => {
    const err = validateFile(file);
    if (err) {
      toast.error(err);
      return;
    }
    setUploadFile(file);
    setPasteText("");
    setApiError("");
  }, []);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect]
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback(() => setDragOver(false), []);

  /* ── Upload submit ── */
  const onSubmitUpload = async () => {
    setApiError("");
    setResult(null);
    setUploading(true);

    try {
      let logContent = "";
      let filename = "pasted_log";

      if (uploadFile) {
        logContent = await uploadFile.text();
        filename = uploadFile.name;
      } else if (pasteText.trim()) {
        logContent = pasteText.trim();
      } else {
        toast.error("Drop a log file or paste log content first.");
        setUploading(false);
        return;
      }

      if (logContent.length < 50) {
        toast.error("Log content is too short. Provide a meaningful Jenkins log.");
        setUploading(false);
        return;
      }

      const data = await analyzeLogText(logContent, filename);
      setResult({
        response: data.response ?? "No analysis text returned.",
        jobName: data.job_name,
        buildNumber: data.build_number,
      });
      toast.success("Log analysis completed successfully.");
      setUploadFile(null);
      setPasteText("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (error) {
      const msg =
        error instanceof Error
          ? error.message
          : "Unexpected error analyzing log.";
      setApiError(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  };

  const busy = isSubmitting || uploading;

  /* ── Tab styling ── */
  const tabClass = (tab: TabMode) =>
    `flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-lg transition-all cursor-pointer ${
      mode === tab
        ? "bg-hpe-green-500 text-white shadow-sm"
        : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
    }`;

  return (
    <div className="space-y-5">
      {/* ── Mode Tabs ── */}
      <div className="flex gap-2">
        <button type="button" className={tabClass("job")} onClick={() => setMode("job")}>
          <Workflow className="h-4 w-4" />
          Analyze from Jenkins
        </button>
        <button type="button" className={tabClass("upload")} onClick={() => setMode("upload")}>
          <Upload className="h-4 w-4" />
          Upload / Paste Log
        </button>
      </div>

      {/* ── Job Mode ── */}
      {mode === "job" && (
        <>
          {jobsError ? (
          <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Jobs unavailable</AlertTitle>
              <AlertDescription>{jobsError}</AlertDescription>
            </Alert>
          ) : null}

          {jobsLoading ? <FormLoadingSkeleton rows={4} /> : null}

          {!jobsLoading && !jobsError && jobOptions.length === 0 ? (
            <EmptyState
              title="No Jenkins jobs found"
              description="You can still continue by typing a Job ID manually below."
              icon={<Database className="h-5 w-5" />}
            />
          ) : null}

          {!jobsLoading ? (
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmitJob)}
                className="grid gap-4 md:grid-cols-2"
              >
                <div className="md:col-span-2">
                  {jobOptions.length > 0 ? (
                    <RHFSelectField
                      control={form.control}
                      name="jobId"
                      label="Select Jenkins Job"
                      placeholder="Select a Jenkins job..."
                      options={jobOptions}
                      description="Required. Choose the Jenkins job to analyze."
                      icon={<Workflow className="h-4 w-4" />}
                    />
                  ) : (
                    <RHFTextField
                      control={form.control}
                      name="jobId"
                      label="Jenkins Job ID"
                      placeholder="Enter job id (for example: 67b2...)"
                      description="No jobs found from API. Enter the backend job ID manually."
                      icon={<Workflow className="h-4 w-4" />}
                    />
                  )}
                </div>

                <div className="md:col-span-2">
                  <RHFTextField
                    control={form.control}
                    name="jenkinsUrl"
                    label="Jenkins URL"
                    placeholder="https://jenkins.example.com"
                    type="url"
                    icon={<Link2 className="h-4 w-4" />}
                  />
                </div>

                <RHFTextField
                  control={form.control}
                  name="username"
                  label="Jenkins Username"
                  placeholder="your-jenkins-username"
                  icon={<UserRound className="h-4 w-4" />}
                />

                <RHFTextField
                  control={form.control}
                  name="password"
                  label="Jenkins Password / API Token"
                  placeholder="your-password-or-api-token"
                  type="password"
                  icon={<KeyRound className="h-4 w-4" />}
                />

                <div className="md:col-span-2 pt-2">
                  <Button
                    type="submit"
                    disabled={busy || jobsLoading}
                    className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Analyzing Latest Build…
                      </>
                    ) : (
                      "Analyze Latest Jenkins Build"
                    )}
                  </Button>
                </div>
              </form>
            </Form>
          ) : null}
        </>
      )}

      {/* ── Upload / Paste Mode ── */}
      {mode === "upload" && (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onClick={() => fileInputRef.current?.click()}
            className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer ${
              dragOver
                ? "border-hpe-green-500 bg-hpe-green-500/5"
                : "border-slate-300 bg-slate-50 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800/50 dark:hover:border-slate-500"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.log,.out,.console"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFileSelect(f);
              }}
            />

            <div className="rounded-full bg-slate-200 p-3 dark:bg-slate-700">
              <Upload className="h-6 w-6 text-slate-500 dark:text-slate-400" />
            </div>

            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
                Drag &amp; drop a build log file here
              </p>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                or click to browse · .txt, .log, .out, .console · max 20 MB
              </p>
            </div>
          </div>

          {/* Selected file indicator */}
          {uploadFile && (
            <div className="flex items-center gap-2 rounded-lg border border-hpe-green-500/30 bg-hpe-green-500/5 px-4 py-2.5">
              <FileText className="h-4 w-4 text-hpe-green-600" />
              <span className="flex-1 truncate text-sm font-medium text-slate-700 dark:text-slate-200">
                {uploadFile.name}
              </span>
              <span className="text-xs text-slate-500">
                {(uploadFile.size / 1024).toFixed(1)} KB
              </span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setUploadFile(null);
                }}
                className="ml-1 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )}

          {/* Divider */}
          <div className="flex items-center gap-3">
            <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            <span className="text-xs font-medium text-slate-400">OR PASTE LOG CONTENT</span>
            <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
          </div>

          {/* Paste area */}
          <textarea
            placeholder="Paste your Jenkins build log here…"
            value={pasteText}
            onChange={(e) => {
              setPasteText(e.target.value);
              if (e.target.value.trim()) setUploadFile(null);
            }}
            rows={6}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 font-mono text-xs leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-hpe-green-500 focus:outline-none focus:ring-1 focus:ring-hpe-green-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:placeholder:text-slate-500"
          />

          {/* Submit */}
          <Button
            type="button"
            onClick={onSubmitUpload}
            disabled={busy || (!uploadFile && !pasteText.trim())}
            className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90"
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing Log…
              </>
            ) : (
              "Analyze Uploaded Log"
            )}
          </Button>
        </div>
      )}

      {/* ── Shared: Errors & Result ── */}
      {apiError ? (
        <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Analysis failed</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      ) : null}

      {result ? (
        <AnalysisResultCard
          response={result.response}
          jobName={result.jobName}
          buildNumber={result.buildNumber}
        />
      ) : null}
    </div>
  );
}
