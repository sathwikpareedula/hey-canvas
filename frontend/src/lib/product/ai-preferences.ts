import { PRODUCT_STORAGE_KEYS } from "@/lib/product/storage-keys";

export type AiProcessingMode = "local" | "cloud";

export type LocalModelTier = "lightweight" | "recommended" | "higher_quality";

export interface AiPreferences {
  version: 1;
  processingMode: AiProcessingMode;
  /** User-selected tier hint — backend chooses compatible models. */
  localModelTier: LocalModelTier;
  updatedAt: string;
}

const DEFAULT: AiPreferences = {
  version: 1,
  processingMode: "local",
  localModelTier: "recommended",
  updatedAt: new Date(0).toISOString(),
};

export function readAiPreferences(): AiPreferences {
  if (typeof window === "undefined") return DEFAULT;
  try {
    const raw = window.localStorage.getItem(PRODUCT_STORAGE_KEYS.aiPreferences);
    if (!raw) return DEFAULT;
    const parsed = JSON.parse(raw) as AiPreferences;
    if (parsed?.version !== 1) return DEFAULT;
    return {
      version: 1,
      processingMode: parsed.processingMode === "cloud" ? "cloud" : "local",
      localModelTier:
        parsed.localModelTier === "lightweight" ||
        parsed.localModelTier === "higher_quality"
          ? parsed.localModelTier
          : "recommended",
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : DEFAULT.updatedAt,
    };
  } catch {
    return DEFAULT;
  }
}

export function writeAiPreferences(prefs: AiPreferences): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PRODUCT_STORAGE_KEYS.aiPreferences, JSON.stringify(prefs));
}

export function saveAiPreferences(patch: Partial<Omit<AiPreferences, "version" | "updatedAt">>): AiPreferences {
  const current = readAiPreferences();
  const next: AiPreferences = {
    version: 1,
    processingMode: patch.processingMode ?? current.processingMode,
    localModelTier: patch.localModelTier ?? current.localModelTier,
    updatedAt: new Date().toISOString(),
  };
  writeAiPreferences(next);
  return next;
}

export function localModelTierLabel(tier: LocalModelTier): string {
  switch (tier) {
    case "lightweight":
      return "Lightweight";
    case "recommended":
      return "Recommended";
    case "higher_quality":
      return "Higher quality";
    default:
      return "Recommended";
  }
}
