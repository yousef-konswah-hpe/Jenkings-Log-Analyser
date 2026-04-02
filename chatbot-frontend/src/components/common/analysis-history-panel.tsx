"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, Eye, FileCode, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AnalysisResultCard } from "@/components/common/analysis-result-card";
import {
  getAnalysisHistory,
  getAnalysisById,
  deleteAnalysis,
  type AnalysisHistoryItem,
} from "@/lib/api";

export function AnalysisHistoryPanel() {
  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAnalysis, setSelectedAnalysis] = useState<{
    analysis: string;
    job_name: string;
    build_number: string;
    log_content?: string;
  } | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getAnalysisHistory();
      setItems(data);
    } catch {
      // silently fail — panel just shows "no analyses yet"
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleView = async (id: string) => {
    setViewingId(id);
    try {
      const detail = await getAnalysisById(id);
      setSelectedAnalysis({
        analysis: detail.analysis,
        job_name: detail.job_name,
        build_number: detail.build_number,
        log_content: detail.log_content,
      });
      setShowLog(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load analysis.");
    } finally {
      setViewingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteAnalysis(id);
      setItems((prev) => prev.filter((item) => item.id !== id));
      if (selectedAnalysis) setSelectedAnalysis(null);
      toast.success("Analysis deleted.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete analysis.");
    } finally {
      setDeletingId(null);
    }
  };

  const formatTimestamp = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return ts;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with refresh */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {loading ? "Loading…" : `${items.length} previous ${items.length === 1 ? "analysis" : "analyses"}`}
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={fetchHistory}
          disabled={loading}
          className="h-8 gap-1.5 text-xs"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* History list */}
      {!loading && items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center dark:border-slate-700 dark:bg-slate-900/60">
          <Clock className="mx-auto mb-2 h-6 w-6 text-slate-400" />
          <p className="text-sm font-medium text-slate-600 dark:text-slate-300">No analyses yet</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Analyze a Jenkins build or upload a log to see results here.
          </p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item) => (
            <Card
              key={item.id}
              className="border-slate-200 bg-white shadow-sm transition hover:border-hpe-green-500/40 dark:border-slate-700 dark:bg-slate-900"
            >
              <CardContent className="flex items-start gap-3 p-4">
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">
                      {item.job_name}
                    </span>
                    <Badge variant="outline" className="text-[10px] h-5">
                      Build #{item.build_number}
                    </Badge>
                    <span className="text-[11px] text-slate-400 dark:text-slate-500">
                      {formatTimestamp(item.timestamp)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed">
                    {item.preview}
                  </p>
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleView(item.id)}
                    disabled={viewingId === item.id}
                    className="h-8 w-8 p-0"
                    title="View full analysis"
                  >
                    {viewingId === item.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Eye className="h-3.5 w-3.5" />
                    )}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleDelete(item.id)}
                    disabled={deletingId === item.id}
                    className="h-8 w-8 p-0 text-red-500 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950"
                    title="Delete analysis"
                  >
                    {deletingId === item.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {/* Expanded view */}
      {selectedAnalysis ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowLog(false)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  !showLog
                    ? "bg-hpe-green-500 text-white shadow-sm"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                Analysis
              </button>
              {selectedAnalysis.log_content ? (
                <button
                  type="button"
                  onClick={() => setShowLog(true)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                    showLog
                      ? "bg-hpe-green-500 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  <FileCode className="h-3 w-3" />
                  Original Log
                </button>
              ) : null}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setSelectedAnalysis(null)}
              className="h-7 text-xs"
            >
              Close
            </Button>
          </div>

          {showLog && selectedAnalysis.log_content ? (
            <Card className="border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                  Original Log — {selectedAnalysis.job_name}
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-hidden">
                <pre className="max-h-[400px] overflow-auto whitespace-pre-wrap break-all rounded-lg bg-slate-950 p-4 text-xs leading-relaxed text-green-400 font-mono">
{selectedAnalysis.log_content}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <AnalysisResultCard
              response={selectedAnalysis.analysis}
              jobName={selectedAnalysis.job_name}
              buildNumber={selectedAnalysis.build_number}
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
