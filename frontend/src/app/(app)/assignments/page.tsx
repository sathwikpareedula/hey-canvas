import { Suspense } from "react";
import { AssignmentsView } from "@/components/assignments/AssignmentsView";
import { PageSkeleton } from "@/components/ui/Skeleton";

export default function AssignmentsPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <AssignmentsView />
    </Suspense>
  );
}
