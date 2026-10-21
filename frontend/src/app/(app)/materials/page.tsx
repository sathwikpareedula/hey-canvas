import { Suspense } from "react";
import { MaterialsView } from "@/components/materials/MaterialsView";
import { PageSkeleton } from "@/components/ui/Skeleton";

export default function MaterialsPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <MaterialsView />
    </Suspense>
  );
}
