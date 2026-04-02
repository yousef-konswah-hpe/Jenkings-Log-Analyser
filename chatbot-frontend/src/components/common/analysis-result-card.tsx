"use client";

import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type ConfidenceMetrics } from "@/lib/api";
import { type BacktrackSimilarity } from "@/lib/result-history";

type AnalysisResultCardProps = {
  response: string;
  jobName?: string;
  buildNumber?: number | string;
  confidence?: ConfidenceMetrics;
  similarity?: BacktrackSimilarity;
};

export function AnalysisResultCard({
  response,
  jobName,
  buildNumber,
  confidence,
  similarity,
}: AnalysisResultCardProps) {
  const [openBubble, setOpenBubble] = useState<"confidence" | "backtrack" | null>(null);
  const confidenceRef = useRef<HTMLDivElement | null>(null);
  const backtrackRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onOutsideClick(event: MouseEvent) {
      if (openBubble === "confidence") {
        if (confidenceRef.current && !confidenceRef.current.contains(event.target as Node)) {
          setOpenBubble(null);
        }
      }
      if (openBubble === "backtrack") {
        if (backtrackRef.current && !backtrackRef.current.contains(event.target as Node)) {
          setOpenBubble(null);
        }
      }
    }

    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpenBubble(null);
      }
    }

    document.addEventListener("mousedown", onOutsideClick);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onOutsideClick);
      document.removeEventListener("keydown", onEscape);
    };
  }, [openBubble]);

  return (
    <Card className="border-hpe-green-500/30 bg-white shadow-sm dark:bg-slate-900">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-xl font-bold text-hpe-blue-900 dark:text-green-300">AI Analysis Result</CardTitle>
          {jobName ? <Badge variant="secondary">{jobName}</Badge> : null}
          {buildNumber !== undefined ? (
            <Badge variant="outline">Build #{String(buildNumber)}</Badge>
          ) : null}
          {confidence ? (
            <div className="relative" ref={confidenceRef}>
              <button
                type="button"
                onClick={() => setOpenBubble((v) => (v === "confidence" ? null : "confidence"))}
                className="cursor-pointer"
              >
                <Badge
                  variant="outline"
                  className="border-emerald-400/40 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
                >
                  Confidence {confidence.score}%
                </Badge>
              </button>

              {openBubble === "confidence" ? (
                <div className="absolute top-10 left-0 z-50 w-[min(28rem,85vw)] rounded-xl border border-emerald-300/40 bg-white p-3 text-xs shadow-xl dark:border-emerald-700/50 dark:bg-slate-900">
                  <div className="absolute -top-2 left-4 h-3 w-3 rotate-45 border-t border-l border-emerald-300/40 bg-white dark:border-emerald-700/50 dark:bg-slate-900" />
                  <p className="font-semibold text-emerald-700 dark:text-emerald-300">Confidence Breakdown</p>
                  <p className="mt-1 text-slate-700 dark:text-slate-200">{confidence.overview}</p>

                  {confidence.quality_dimensions ? (
                    <div className="mt-2 grid grid-cols-2 gap-1 text-slate-700 dark:text-slate-200">
                      <p>Evidence coverage: {confidence.quality_dimensions.evidence_coverage}%</p>
                      <p>Specificity: {confidence.quality_dimensions.specificity}%</p>
                      <p>Structure: {confidence.quality_dimensions.structure}%</p>
                      <p>Certainty: {confidence.quality_dimensions.certainty}%</p>
                    </div>
                  ) : null}

                  {confidence.positive_signals?.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">What improved confidence</p>
                      {confidence.positive_signals.map((item) => (
                        <p key={item} className="text-slate-700 dark:text-slate-200">• {item}</p>
                      ))}
                    </div>
                  ) : null}

                  {confidence.risk_signals?.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">What reduced confidence</p>
                      {confidence.risk_signals.map((item) => (
                        <p key={item} className="text-slate-700 dark:text-slate-200">• {item}</p>
                      ))}
                    </div>
                  ) : null}

                  {confidence.score < 100 && confidence.missing_for_full_confidence?.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">Why this is not 100%</p>
                      {confidence.missing_for_full_confidence.map((item) => (
                        <p key={item} className="text-slate-700 dark:text-slate-200">• {item}</p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
          {similarity ? (
            <div className="relative" ref={backtrackRef}>
              <button
                type="button"
                onClick={() => setOpenBubble((v) => (v === "backtrack" ? null : "backtrack"))}
                className="cursor-pointer"
              >
                <Badge
                  variant="outline"
                  className="border-blue-400/40 bg-blue-50 text-blue-800 dark:bg-blue-950/40 dark:text-blue-300"
                >
                  Backtrack {similarity.comparedCount ? `${similarity.score}%` : "n/a"}
                </Badge>
              </button>

              {openBubble === "backtrack" ? (
                <div className="absolute top-10 left-0 z-50 w-[min(28rem,85vw)] rounded-xl border border-blue-300/40 bg-white p-3 text-xs shadow-xl dark:border-blue-700/50 dark:bg-slate-900">
                  <div className="absolute -top-2 left-4 h-3 w-3 rotate-45 border-t border-l border-blue-300/40 bg-white dark:border-blue-700/50 dark:bg-slate-900" />
                  <p className="font-semibold text-blue-700 dark:text-blue-300">Backtrack Similarity Breakdown</p>
                  <p className="mt-1 text-slate-700 dark:text-slate-200">{similarity.overview}</p>

                  {similarity.exactMatches.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">100% similar results</p>
                      {similarity.exactMatches.map((item) => (
                        <p key={item} className="text-slate-700 dark:text-slate-200">• {item}</p>
                      ))}
                    </div>
                  ) : null}

                  {similarity.topSharedTerms.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">Strong exact overlaps</p>
                      <p className="text-slate-700 dark:text-slate-200">{similarity.topSharedTerms.join(", ")}</p>
                    </div>
                  ) : null}

                  {similarity.synonymousMatches.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">Synonymous similarities</p>
                      {similarity.synonymousMatches.map((item) => (
                        <p key={item} className="text-slate-700 dark:text-slate-200">• {item}</p>
                      ))}
                    </div>
                  ) : null}

                  {similarity.comparisonDetails.length ? (
                    <div className="mt-2">
                      <p className="font-medium text-slate-800 dark:text-slate-100">Compared session results</p>
                      {similarity.comparisonDetails.map((item) => (
                        <p key={item.label} className="text-slate-700 dark:text-slate-200">
                          • {item.label}: {item.score}%
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        {(confidence || similarity) ? (
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Click Confidence or Backtrack badges for full metric breakdown.
          </p>
        ) : null}
      </CardHeader>
      <CardContent>
        <p className="whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">{response}</p>
      </CardContent>
    </Card>
  );
}
