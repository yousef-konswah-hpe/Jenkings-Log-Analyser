"use client";

import { ReactNode, useEffect, useRef, useState } from "react";
import { ThumbsUp, ThumbsDown, Brain, Search, CheckCircle2, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type ConfidenceMetrics, type SimilarAnalysis, type ReActTraceEntry, submitFeedback } from "@/lib/api";
import { type BacktrackSimilarity } from "@/lib/result-history";

function renderBold(text: string): ReactNode[] {
  const parts = text.split(/\*\*(.*?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-bold">
        {part}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

type AnalysisResultCardProps = {
  response: string;
  jobName?: string;
  buildNumber?: number | string;
  confidence?: ConfidenceMetrics;
  similarity?: BacktrackSimilarity;
  similarAnalyses?: SimilarAnalysis[];
  reactTrace?: ReActTraceEntry[];
  analysisId?: string;
};

export function AnalysisResultCard({
  response,
  jobName,
  buildNumber,
  confidence,
  similarity,
  similarAnalyses,
  reactTrace,
  analysisId,
}: AnalysisResultCardProps) {
  const [openBubble, setOpenBubble] = useState<"confidence" | "backtrack" | "rag" | "react" | null>(null);
  const confidenceRef = useRef<HTMLDivElement | null>(null);
  const backtrackRef = useRef<HTMLDivElement | null>(null);
  const ragRef = useRef<HTMLDivElement | null>(null);
  const reactRef = useRef<HTMLDivElement | null>(null);

  // Feedback state
  const [feedbackGiven, setFeedbackGiven] = useState<"positive" | "negative" | null>(null);
  const [showCorrectionInput, setShowCorrectionInput] = useState(false);
  const [correctionText, setCorrectionText] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState("");

  useEffect(() => {
    function onOutsideClick(event: MouseEvent) {
      const refs: Record<string, React.RefObject<HTMLDivElement | null>> = {
        confidence: confidenceRef,
        backtrack: backtrackRef,
        rag: ragRef,
        react: reactRef,
      };
      if (openBubble && refs[openBubble]?.current && !refs[openBubble].current!.contains(event.target as Node)) {
        setOpenBubble(null);
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

  const handleFeedback = async (rating: "positive" | "negative") => {
    if (feedbackGiven) return;
    setFeedbackGiven(rating);

    if (rating === "negative") {
      setShowCorrectionInput(true);
      return; // wait for correction text submission
    }

    // Send positive feedback immediately
    setFeedbackSending(true);
    try {
      const result = await submitFeedback({
        analysis_id: analysisId || "",
        rating,
        job_name: jobName,
      });
      setFeedbackMessage(result.message);
    } catch {
      setFeedbackMessage("Failed to submit feedback.");
    } finally {
      setFeedbackSending(false);
    }
  };

  const handleCorrectionSubmit = async () => {
    setFeedbackSending(true);
    try {
      const result = await submitFeedback({
        analysis_id: analysisId || "",
        rating: "negative",
        correction: correctionText,
        job_name: jobName,
      });
      setFeedbackMessage(result.message);
      setShowCorrectionInput(false);
    } catch {
      setFeedbackMessage("Failed to submit feedback.");
    } finally {
      setFeedbackSending(false);
    }
  };

  const hasRag = similarAnalyses && similarAnalyses.length > 0;
  const hasReact = reactTrace && reactTrace.length > 0;
  const reactIterations = reactTrace?.length ?? 0;

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
                      {similarity.exactMatches.map((item, idx) => (
                        <p key={`exact-match-${idx}`} className="text-slate-700 dark:text-slate-200">• {item}</p>
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

          {/* RAG Badge */}
          {hasRag ? (
            <div className="relative" ref={ragRef}>
              <button
                type="button"
                onClick={() => setOpenBubble((v) => (v === "rag" ? null : "rag"))}
                className="cursor-pointer"
              >
                <Badge
                  variant="outline"
                  className="border-purple-400/40 bg-purple-50 text-purple-800 dark:bg-purple-950/40 dark:text-purple-300"
                >
                  <Search className="mr-1 h-3 w-3" />
                  RAG {similarAnalyses!.length} match{similarAnalyses!.length > 1 ? "es" : ""}
                </Badge>
              </button>

              {openBubble === "rag" ? (
                <div className="absolute top-10 left-0 z-50 w-[min(30rem,85vw)] rounded-xl border border-purple-300/40 bg-white p-3 text-xs shadow-xl dark:border-purple-700/50 dark:bg-slate-900">
                  <div className="absolute -top-2 left-4 h-3 w-3 rotate-45 border-t border-l border-purple-300/40 bg-white dark:border-purple-700/50 dark:bg-slate-900" />
                  <p className="font-semibold text-purple-700 dark:text-purple-300">Similar Past Failures (RAG)</p>
                  <p className="mt-1 text-slate-600 dark:text-slate-300">
                    Found {similarAnalyses!.length} similar past failure{similarAnalyses!.length > 1 ? "s" : ""} via semantic search.
                    The analysis used these to identify recurring patterns.
                  </p>
                  {similarAnalyses!.map((sa, idx) => (
                    <div key={sa.analysis_id} className="mt-2 rounded-lg border border-purple-200/50 bg-purple-50/50 p-2 dark:border-purple-800/30 dark:bg-purple-950/20">
                      <div className="flex items-center justify-between">
                        <p className="font-medium text-slate-800 dark:text-slate-100">
                          #{idx + 1} {sa.job_name}
                        </p>
                        <Badge variant="outline" className="text-[10px] border-purple-300 text-purple-700 dark:border-purple-600 dark:text-purple-300">
                          {sa.similarity}% match
                        </Badge>
                      </div>
                      <p className="mt-1 text-slate-600 dark:text-slate-300 line-clamp-3">
                        {sa.summary_text.slice(0, 200)}…
                      </p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {/* ReAct Badge */}
          {hasReact ? (
            <div className="relative" ref={reactRef}>
              <button
                type="button"
                onClick={() => setOpenBubble((v) => (v === "react" ? null : "react"))}
                className="cursor-pointer"
              >
                <Badge
                  variant="outline"
                  className="border-amber-400/40 bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
                >
                  <Brain className="mr-1 h-3 w-3" />
                  ReAct {reactIterations} step{reactIterations > 1 ? "s" : ""}
                </Badge>
              </button>

              {openBubble === "react" ? (
                <div className="absolute top-10 right-0 z-50 w-[min(28rem,85vw)] rounded-xl border border-amber-300/40 bg-white p-3 text-xs shadow-xl dark:border-amber-700/50 dark:bg-slate-900">
                  <div className="absolute -top-2 right-4 h-3 w-3 rotate-45 border-t border-l border-amber-300/40 bg-white dark:border-amber-700/50 dark:bg-slate-900" />
                  <p className="font-semibold text-amber-700 dark:text-amber-300">ReAct Reasoning Trace</p>
                  <p className="mt-1 text-slate-600 dark:text-slate-300">
                    The AI self-evaluated and refined the report through {reactIterations} iteration{reactIterations > 1 ? "s" : ""}.
                  </p>
                  {reactTrace!.map((step) => (
                    <div key={step.iteration} className="mt-2 rounded-lg border border-amber-200/50 bg-amber-50/50 p-2 dark:border-amber-800/30 dark:bg-amber-950/20">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] border-amber-300 dark:border-amber-600">
                          Step {step.iteration}
                        </Badge>
                        <span className={`text-[10px] font-semibold ${step.action === "PASS" ? "text-green-600" : "text-amber-600"}`}>
                          {step.action === "PASS" ? "✓ Passed" : "↻ Refined"}
                        </span>
                        <span className="text-slate-500">Confidence: {step.confidence_score}%</span>
                      </div>
                      <p className="mt-1 text-slate-600 dark:text-slate-300">{step.details}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
        {(confidence || similarity || hasRag || hasReact) ? (
          <p className="text-xs text-slate-600 dark:text-slate-300">
            Click badges for full metric breakdowns.
            {hasRag ? " RAG found similar past failures." : ""}
            {hasReact ? ` ReAct refined the report in ${reactIterations} step${reactIterations > 1 ? "s" : ""}.` : ""}
          </p>
        ) : null}
      </CardHeader>
      <CardContent>
        <div className="whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">
          {renderBold(response)}
        </div>

        {/* Feedback Section */}
        <div className="mt-6 border-t border-slate-200 pt-4 dark:border-slate-700">
          {!feedbackGiven && !feedbackMessage ? (
            <div className="flex items-center gap-3">
              <p className="text-sm text-slate-600 dark:text-slate-300">Was this analysis helpful?</p>
              <button
                type="button"
                onClick={() => handleFeedback("positive")}
                disabled={feedbackSending}
                className="flex items-center gap-1.5 rounded-lg border border-green-300 bg-green-50 px-3 py-1.5 text-sm text-green-700 transition hover:bg-green-100 dark:border-green-700 dark:bg-green-950/30 dark:text-green-300 dark:hover:bg-green-900/40"
              >
                <ThumbsUp className="h-4 w-4" /> Yes
              </button>
              <button
                type="button"
                onClick={() => handleFeedback("negative")}
                disabled={feedbackSending}
                className="flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-1.5 text-sm text-red-700 transition hover:bg-red-100 dark:border-red-700 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-900/40"
              >
                <ThumbsDown className="h-4 w-4" /> No
              </button>
            </div>
          ) : null}

          {showCorrectionInput ? (
            <div className="mt-3 space-y-2">
              <p className="text-sm text-slate-600 dark:text-slate-300">
                What was wrong? Your correction helps the AI learn.
              </p>
              <textarea
                value={correctionText}
                onChange={(e) => setCorrectionText(e.target.value)}
                placeholder="e.g. The root cause was actually a DNS resolution failure, not a timeout..."
                className="w-full rounded-lg border border-slate-300 bg-white p-2 text-sm outline-none focus:border-amber-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
                rows={3}
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleCorrectionSubmit}
                  disabled={feedbackSending}
                  className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-sm text-white transition hover:bg-amber-600 disabled:opacity-50"
                >
                  {feedbackSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                  Submit Correction
                </button>
                <button
                  type="button"
                  onClick={() => { handleCorrectionSubmit(); }}
                  disabled={feedbackSending || !correctionText.trim()}
                  className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                >
                  Skip & send without correction
                </button>
              </div>
            </div>
          ) : null}

          {feedbackMessage ? (
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              <span className="text-slate-600 dark:text-slate-300">{feedbackMessage}</span>
              {feedbackGiven === "positive" ? (
                <ThumbsUp className="h-4 w-4 text-green-500" />
              ) : (
                <ThumbsDown className="h-4 w-4 text-amber-500" />
              )}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
