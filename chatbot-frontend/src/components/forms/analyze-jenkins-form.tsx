"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { RHFSelectField, RHFTextField } from "@/components/forms/form-fields";

const analyzeSchema = z.object({
  jobId: z.string().min(1, "Please select a Jenkins job."),
  jenkinsUrl: z
    .string()
    .trim()
    .optional()
    .refine((v) => !v || /^https?:\/\/.+/i.test(v), "Please enter a valid URL starting with http:// or https://."),
  username: z.string().trim().optional(),
  password: z.string().trim().optional(),
});

type AnalyzeFormValues = z.infer<typeof analyzeSchema>;

const jobOptions = [
  { label: "System-Security-Test", value: "System-Security-Test" },
  { label: "Report-Management", value: "Report-Management" },
  { label: "Sustainability-Dashboard", value: "Sustainability-Dashboard" },
];

export function AnalyzeJenkinsForm() {
  const [result, setResult] = useState<string>("");

  const form = useForm<AnalyzeFormValues>({
    resolver: zodResolver(analyzeSchema),
    defaultValues: {
      jobId: "",
      jenkinsUrl: "",
      username: "",
      password: "",
    },
    mode: "onChange",
  });

  const onSubmit = async (values: AnalyzeFormValues) => {
    setResult("");

    // Step 4: validated UI flow (backend wiring in next step)
    await new Promise((resolve) => setTimeout(resolve, 800));

    setResult(
      `Validated request for ${values.jobId}. Ready to send analysis request to backend API.`
    );
  };

  const isSubmitting = form.formState.isSubmitting;

  return (
    <div className="space-y-5">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-4 md:grid-cols-2">
          <div className="md:col-span-2">
            <RHFSelectField
              control={form.control}
              name="jobId"
              label="Select Jenkins Job"
              placeholder="Select a Jenkins job..."
              options={jobOptions}
              description="Required. Choose the Jenkins job to analyze."
            />
          </div>

          <div className="md:col-span-2">
            <RHFTextField
              control={form.control}
              name="jenkinsUrl"
              label="Jenkins URL"
              placeholder="https://jenkins.example.com"
              type="url"
            />
          </div>

          <RHFTextField
            control={form.control}
            name="username"
            label="Jenkins Username"
            placeholder="your-jenkins-username"
          />

          <RHFTextField
            control={form.control}
            name="password"
            label="Jenkins Password / API Token"
            placeholder="your-password-or-api-token"
            type="password"
          />

          <div className="md:col-span-2 pt-2">
            <Button
              type="submit"
              disabled={isSubmitting}
              className="h-11 w-full bg-hpe-green-500 text-white hover:opacity-90"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Validating...
                </>
              ) : (
                "Analyze Latest Jenkins Build"
              )}
            </Button>
          </div>
        </form>
      </Form>

      {result ? (
        <Alert className="border-hpe-green-500/40 bg-white">
          <Sparkles className="h-4 w-4 text-hpe-green-500" />
          <AlertTitle>Validation success</AlertTitle>
          <AlertDescription>{result}</AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
