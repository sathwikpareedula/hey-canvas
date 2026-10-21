import type { ProductReadiness } from "@/lib/domain/product-settings";

export function localAiBlocksStartup(
  readiness: ProductReadiness | null,
  aiMode: "local" | "cloud",
): boolean {
  if (aiMode === "cloud") return false;
  const runtime = readiness?.checks.find((c) => c.component === "local_ai_runtime");
  const model = readiness?.checks.find((c) => c.component === "local_ai_model");
  if (!runtime && !model) return false;
  const blocked =
    runtime?.status === "unavailable" ||
    runtime?.status === "action_required" ||
    model?.status === "action_required";
  return Boolean(blocked);
}
