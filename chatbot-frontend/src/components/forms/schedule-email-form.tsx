"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, Database, Loader2, MailCheck } from "lucide-react";
import { toast } from "sonner";

import { Form } from "@/components/ui/form";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { EmptyState } from "@/components/common/empty-state";
import { FormLoadingSkeleton } from "@/components/common/form-loading-skeleton";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";
import { useJenkinsJobs } from "@/hooks/use-jenkins-jobs";
import { scheduleEmailReport } from "@/lib/api";

const scheduleSchema = z.object({
  jobId: z.string().min(1, "Please select a Jenkins job."),
  email: z.string().trim().email("Please enter a valid recipient email."),
  frequency: z.enum(["immediate", "hourly", "daily", "weekly", "monthly"]),
});

type ScheduleFormValues = z.infer<typeof scheduleSchema>;

const frequencyOptions: { label: string; value: ScheduleFormValues["frequency"] }[] = [
  { label: "Send Immediately", value: "immediate" },
  { label: "Hourly", value: "hourly" },
  { label: "Daily", value: "daily" },
  { label: "Weekly", value: "weekly" },
  { label: "Monthly", value: "monthly" },
];

export function ScheduleEmailForm() {
  const { jobs, loading: jobsLoading, error: jobsError } = useJenkinsJobs();
  const [apiError, setApiError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const form = useForm<ScheduleFormValues>({
    resolver: zodResolver(scheduleSchema),
    defaultValues: {
      jobId: "",
      email: "",
      frequency: "immediate",
    },
    mode: "onChange",
  });

  const jobOptions = jobs.map((job) => ({
    label: job.display_name,
    value: job.id,
  }));

  const isSubmitting = form.formState.isSubmitting;

  const onSubmit = async (values: ScheduleFormValues) => {
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
    } catch (e) {
      const message =
        e instanceof Error ? e.message : "Unexpected error while scheduling email."
      setApiError(message);
      toast.error(message);
    }
  };

  return (
    <div className="space-y-5">
      {jobsError ? (
        <Alert variant="destructive" className="border-red-300 bg-white">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Jobs unavailable</AlertTitle>
          <AlertDescription>{jobsError}</AlertDescription>
        </Alert>
      ) : null}

      {jobsLoading ? <FormLoadingSkeleton rows={3} /> : null}

      {!jobsLoading && !jobsError && jobOptions.length === 0 ? (
        <EmptyState
          title="No Jenkins jobs found"
          description="Add at least one Jenkins job in the backend before scheduling reports."
          icon={<Database className="h-5 w-5" />}
        />
      ) : null}

      {!jobsLoading && jobOptions.length > 0 ? (
        <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <RHFSelectField
              control={form.control}
              name="jobId"
              label="Select Jenkins Job"
              placeholder={jobsLoading ? "Loading jobs..." : "Select a Jenkins job..."}
              options={jobOptions}
            />
          </div>

          <div className="md:col-span-2">
            <RHFTextField
              control={form.control}
              name="email"
              label="Recipient Email"
              placeholder="user@example.com"
              type="text"
            />
          </div>

          <div className="md:col-span-2">
            <RHFSelectField
              control={form.control}
              name="frequency"
              label="Frequency"
              placeholder="Choose frequency"
              options={frequencyOptions}
            />
          </div>

          <div className="md:col-span-2 pt-2">
            <Button
              type="submit"
              disabled={isSubmitting || jobsLoading || jobOptions.length === 0}
              className="h-11 w-full bg-hpe-blue-700 text-white hover:opacity-90"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Submitting...
                </>
              ) : (
                "Schedule/Send Email Report"
              )}
            </Button>
          </div>
        </form>
      </Form>
      ) : null}

      {apiError ? (
        <Alert variant="destructive" className="border-red-300 bg-white">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Email request failed</AlertTitle>
          <AlertDescription>{apiError}</AlertDescription>
        </Alert>
      ) : null}

      {successMessage ? (
        <Alert className="border-hpe-green-500/40 bg-white">
          <MailCheck className="h-4 w-4 text-hpe-green-500" />
          <AlertTitle>Email request submitted</AlertTitle>
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
