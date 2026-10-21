export type ApiMode = "mock" | "http";

/** Personal/local use is the default; demo requires an explicit flag. */
export function getApiMode(): ApiMode {
  const mode = process.env.NEXT_PUBLIC_ACADEMIC_API_MODE;
  if (mode === "mock") return "mock";
  return "http";
}

export function isExplicitDemoMode(): boolean {
  return (
    process.env.NEXT_PUBLIC_ACADEMIC_API_MODE === "mock" ||
    process.env.NEXT_PUBLIC_HEY_CANVAS_DEMO === "1"
  );
}
