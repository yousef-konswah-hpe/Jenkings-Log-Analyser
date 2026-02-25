export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:5005";

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
