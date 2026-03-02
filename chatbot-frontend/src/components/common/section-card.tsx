import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SectionCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function SectionCard({ title, description, children }: SectionCardProps) {
  return (
    <Card className="border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <CardHeader className="pb-3">
        <CardTitle className="text-2xl font-bold text-hpe-blue-900 dark:text-green-300">{title}</CardTitle>
        {description ? (
          <p className="text-base font-semibold text-slate-700 dark:text-slate-300">{description}</p>
        ) : null}
      </CardHeader>
      <CardContent className="text-base leading-7 text-slate-800 dark:text-slate-100">
        {children}
      </CardContent>
    </Card>
  );
}
