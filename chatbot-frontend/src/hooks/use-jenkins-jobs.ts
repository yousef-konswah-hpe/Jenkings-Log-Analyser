"use client";

import { useEffect, useState } from "react";
import { getJenkinsJobs, JenkinsJob } from "@/lib/api";

export function useJenkinsJobs() {
  const [jobs, setJobs] = useState<JenkinsJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    async function loadJobs() {
      try {
        setLoading(true);
        setError("");
        const data = await getJenkinsJobs();
        if (mounted) {
          setJobs(data);
        }
      } catch (e) {
        if (mounted) {
          setError(e instanceof Error ? e.message : "Failed to load Jenkins jobs.");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadJobs();

    return () => {
      mounted = false;
    };
  }, []);

  return { jobs, loading, error };
}
