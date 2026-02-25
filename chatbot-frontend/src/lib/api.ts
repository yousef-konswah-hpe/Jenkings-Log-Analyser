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

export type AnalyzeApiResponse = {
  success: boolean;
  response?: string;
  job_name?: string;
  build_number?: number | string;
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
