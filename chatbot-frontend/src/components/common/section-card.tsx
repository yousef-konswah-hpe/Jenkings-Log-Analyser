import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type SectionCardProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function SectionCard({ title, description, children }: SectionCardProps) {
  return (
    <Card className="border-slate-200 bg-white shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-2xl font-bold text-hpe-blue-900">{title}</CardTitle>
        {description ? <p className="text-base font-medium text-slate-700">{description}</p> : null}
      </CardHeader>
      <CardContent className="text-base leading-7 text-slate-800">{children}</CardContent>
    </Card>
  );
}
