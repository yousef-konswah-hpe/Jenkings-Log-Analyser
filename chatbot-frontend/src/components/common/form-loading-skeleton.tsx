import { Skeleton } from "@/components/ui/skeleton";

type FormLoadingSkeletonProps = {
  rows?: number;
};

export function FormLoadingSkeleton({ rows = 4 }: FormLoadingSkeletonProps) {
  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="space-y-2">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-11 w-full" />
        </div>
      ))}
    </div>
  );
}
