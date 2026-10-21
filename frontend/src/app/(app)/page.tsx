import { Suspense } from "react";
import { HeyCanvasWorkspace } from "@/components/hey-canvas/HeyCanvasWorkspace";
import { PageSkeleton } from "@/components/ui/Skeleton";

export default function HomePage() {
  return (
    <div className="-my-6 flex min-h-0 flex-1 flex-col overflow-hidden md:-my-6">
      <Suspense fallback={<PageSkeleton />}>
        <HeyCanvasWorkspace />
      </Suspense>
    </div>
  );
}
