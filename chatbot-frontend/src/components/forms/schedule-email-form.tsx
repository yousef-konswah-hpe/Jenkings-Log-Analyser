"use client";

import { useCallback, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle,
  CalendarClock,
  Database,
  FileText,
  Loader2,
  Mail,
  MailCheck,
  Upload,
  Workflow,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Form } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EmptyState } from "@/components/common/empty-state";
import { FormLoadingSkeleton } from "@/components/common/form-loading-skeleton";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";
import { useJenkinsJobs } from "@/hooks/use-jenkins-jobs";
import { scheduleEmailReport, emailLogReport } from "@/lib/api";

/* ── Schemas ── */
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

const ACCEPTED_EXTENSIONS = [".txt", ".log", ".out", ".console"];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

/* ── Component ── */
export function ScheduleEmailForm() {
  const { jobs, loading: jobsLoading, error: jobsError } = useJenkinsJobs();

  const [mode, setMode] = useState<TabMode>("job");
  const [apiError, setApiError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  /* upload state */
  const [dragOver, setDragOver] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [pasteText, setPasteText] = useState("");
  const [uploadEmail, setUploadEmail] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* job form */
  const form = useForm<ScheduleFormValues>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: { jobId: "", email: "", frequency: "immediate" },
    mode: "onChange",
  });

  const jobOptions = jobs.map((job) => ({
    label: job.display_name,
    value: job.id,
  }));

  const isSubmitting = form.formState.isSubmitting;

  /* ── Job-based submit ── */
  const onSubmitJob = async (values: ScheduleFormValues) => {
    setApiError("");
    setSuccessMessage("");
    try {
      const response = await scheduleEmailReport({
        jobId: values.jobId,
        email: values.email,
        frequency: values.frequency === "immediate" ? undefined : values.frequency,
      });
      setSuccessMessage(response.message);
      toast.success(response.message);
      form.reset();
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Unexpected error while scheduling email.";
      setApiError(message);
      toast.error(message);
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
    setSuccessMessage("");
    setUploading(true);

    try {
      if (!uploadEmail.trim() || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(uploadEmail.trim())) {
        toast.error("Please enter a valid email address.");
        setUploading(false);
        return;
      }

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

      const data = await emailLogReport(logContent, uploadEmail.trim(), filename);
      setSuccessMessage(data.message);
      toast.success(data.message);
      setUploadFile(null);
      setPasteText("");
      setUploadEmail("");
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (error) {
      const msg =
        error instanceof Error ? error.message : "Unexpected error emailing report.";
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
          From Jenkins Job
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

          {jobsLoading ? <FormLoadingSkeleton rows={3} /> : null}

          {!jobsLoading && !jobsError && jobOptions.length === 0 ? (
            <EmptyState
              title="No Jenkins jobs found"
              description="You can still continue by typing a Job ID manually below."
              icon={<Database className="h-5 w-5" />}
            />
          ) : null}

          {!jobsLoading ? (
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmitJob)} className="grid gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  {jobOptions.length > 0 ? (
                    <RHFSelectField
                      control={form.control}
                      name="jobId"
                      label="Select Jenkins Job"
                      placeholder="Select a Jenkins job..."
                      options={jobOptions}
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
                    name="email"
                    label="Recipient Email"
                    placeholder="user@example.com"
                    type="text"
                    icon={<Mail className="h-4 w-4" />}
                  />
                </div>

                <div className="md:col-span-2">
                  <RHFSelectField
                    control={form.control}
                    name="frequency"
                    label="Frequency"
                    placeholder="Choose frequency"
                    options={frequencyOptions}
                    icon={<CalendarClock className="h-4 w-4" />}
                  />
                </div>

                <div className="md:col-span-2 pt-2">
                  <Button
                    type="submit"
                    disabled={busy || jobsLoading}
                    className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Submitting…
                      </>
                    ) : (
                      "Schedule / Send Email Report"
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
                type="email"
                placeholder="user@example.com"
                value={uploadEmail}
                onChange={(e) => setUploadEmail(e.target.value)}
                className="h-11 w-full rounded-md border border-slate-300 bg-white pl-10 pr-4 text-sm text-slate-800 placeholder:text-slate-400 focus:border-hpe-green-500 focus:outline-none focus:ring-1 focus:ring-hpe-green-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
              />
            </div>
          </div>

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
            rows={5}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 font-mono text-xs leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-hpe-green-500 focus:outline-none focus:ring-1 focus:ring-hpe-green-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:placeholder:text-slate-500"
          />

          {/* Submit */}
          <Button
            type="button"
            onClick={onSubmitUpload}
            disabled={busy || (!uploadFile && !pasteText.trim()) || !uploadEmail.trim()}
            className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90"
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Analyzing &amp; Emailing…
              </>
            ) : (
              "Analyze & Email Report"
            )}
          </Button>
        </div>
      )}

      {/* ── Shared: Errors & Success ── */}
      {apiError ? (
        <Alert variant="destructive" className="border-red-300 bg-white dark:bg-slate-900 dark:border-red-500/40">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Email request failed</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      ) : null}

      {successMessage ? (
        <Alert className="border-hpe-green-500/40 bg-white dark:bg-slate-900 dark:border-hpe-green-500/30">
          <MailCheck className="h-4 w-4 text-hpe-green-500" />
          <AlertTitle>Email request submitted</AlertTitle>
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
