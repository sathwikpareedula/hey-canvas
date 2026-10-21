export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded-md bg-[var(--surface-muted)] motion-reduce:animate-none ${className}`}
      aria-hidden
    />
  );
}

export function PageSkeleton() {
  return (
    <div className="mx-auto max-w-3xl space-y-4" role="status" aria-label="Loading">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
