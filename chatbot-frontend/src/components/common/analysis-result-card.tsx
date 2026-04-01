import { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Turn **text** into <strong>text</strong>, leave the rest as plain text. */
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
};

export function AnalysisResultCard({
  response,
  jobName,
  buildNumber,
}: AnalysisResultCardProps) {
  return (
    <Card className="border-hpe-green-500/30 bg-white shadow-sm dark:bg-slate-900">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-xl font-bold text-hpe-blue-900 dark:text-green-300">AI Analysis Result</CardTitle>
          {jobName ? <Badge variant="secondary">{jobName}</Badge> : null}
          {buildNumber !== undefined ? (
            <Badge variant="outline">Build #{String(buildNumber)}</Badge>
          ) : null}
        </div>
      </CardHeader>
      <CardContent>
        <div className="whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">
          {renderBold(response)}
        </div>
      </CardContent>
    </Card>
  );
}
