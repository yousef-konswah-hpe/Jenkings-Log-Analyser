export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5005";

export type JenkinsJob = {
  id: string;
  display_name: string;
  description?: string;
};

type JenkinsJobsResponse = {
  success: boolean;
  jobs?: JenkinsJob[];
  error?: string;
};

export type AnalyzeApiRequest = {
  job_id: string;
  jenkins_url?: string;
  username?: string;
  password?: string;
};

export type ConfidenceMetrics = {
  score: number;
  label: "low" | "medium" | "high";
  overview: string;
  details: string[];
  positive_signals?: string[];
  risk_signals?: string[];
  missing_for_full_confidence?: string[];
  quality_dimensions?: {
    evidence_coverage: number;
    specificity: number;
    structure: number;
    certainty: number;
  };
};

export type AnalyzeApiResponse = {
  success: boolean;
  response?: string;
  job_name?: string;
  build_number?: number | string;
  confidence?: ConfidenceMetrics;
  error?: string;
};

export type ScheduleEmailRequest = {
  jobId: string;
  email: string;
  frequency?: "hourly" | "daily" | "weekly" | "monthly";
};

type ScheduleEmailResponse = {
  message?: string;
  error?: string;
};

type SupportChatResponse = {
  success: boolean;
  response?: string;
  error?: string;
};

export async function getJenkinsJobs(): Promise<JenkinsJob[]> {
  const res = await fetch(`${API_BASE_URL}/api/jobs`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  const raw = await res.text();
  let data: JenkinsJobsResponse;

  try {
    data = JSON.parse(raw) as JenkinsJobsResponse;
  } catch {
    throw new Error(raw || "Invalid response from jobs API.");
  }

  if (!res.ok || !data.success) {
    throw new Error(data.error || "Failed to load Jenkins jobs.");
  }

  return data.jobs ?? [];
}

export async function analyzeJenkinsBuild(
  payload: AnalyzeApiRequest
): Promise<AnalyzeApiResponse> {
  const res = await fetch(`${API_BASE_URL}/api/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const raw = await res.text();
  let data: AnalyzeApiResponse;

  try {
    data = JSON.parse(raw) as AnalyzeApiResponse;
  } catch {
    throw new Error(raw || "Invalid response from backend API.");
  }

  if (!res.ok || !data.success) {
    throw new Error(data.error || "Failed to analyze Jenkins job.");
  }

  return data;
}

export async function scheduleEmailReport(
  payload: ScheduleEmailRequest
): Promise<{ message: string }> {
  const body: { email: string; frequency?: string } = {
    email: payload.email,
  };

  if (payload.frequency) {
    body.frequency = payload.frequency;
  }

  const res = await fetch(`${API_BASE_URL}/schedule-email/${payload.jobId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const raw = await res.text();
  let data: ScheduleEmailResponse;

  try {
    data = JSON.parse(raw) as ScheduleEmailResponse;
  } catch {
    throw new Error(raw || "Invalid response from schedule email API.");
  }

  if (!res.ok) {
    throw new Error(data.error || "Failed to schedule/send email report.");
  }

  return {
    message: data.message || "Email request completed successfully.",
  };
}

export async function analyzeLogText(
  logText: string,
  filename?: string
): Promise<AnalyzeApiResponse> {
  const res = await fetch(`${API_BASE_URL}/api/analyze-log`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ log_text: logText, filename }),
  });

  const raw = await res.text();
  let data: AnalyzeApiResponse;

  try {
    data = JSON.parse(raw) as AnalyzeApiResponse;
  } catch {
    throw new Error(raw || "Invalid response from log analysis API.");
  }

  if (!res.ok || !data.success) {
    throw new Error(data.error || "Failed to analyze log content.");
  }

  return data;
}

export async function emailLogReport(
  logText: string,
  email: string,
  filename?: string
): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE_URL}/api/email-log-report`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ log_text: logText, email, filename }),
  });

  const raw = await res.text();
  let data: { success?: boolean; message?: string; error?: string };

  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error(raw || "Invalid response from email-log-report API.");
  }

  if (!res.ok || !data.success) {
    throw new Error(data.error || "Failed to email log report.");
  }

  return { message: data.message || "Email report sent." };
}

export async function getSupportChatReply(
  message: string,
  context?: Record<string, string>
): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/api/chat/support`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, context }),
  });

  const raw = await res.text();
  let data: SupportChatResponse;

  try {
    data = JSON.parse(raw) as SupportChatResponse;
  } catch {
    throw new Error(raw || "Invalid response from support chat API.");
  }

  if (!res.ok || !data.success) {
    throw new Error(data.error || "Failed to get support chat response.");
  }

  return data.response || "No response from assistant.";
}
