"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { formatRelativeTime } from "@/lib/utils/date";
import {
  getProductSettingsApi,
  loadProductSettings,
  loadReadiness,
  saveProductSettings,
  type LoadedProductSettings,
  type SettingsSource,
} from "@/lib/api/product-settings-service";
import type { ProductReadiness, ProductSettings } from "@/lib/domain/product-settings";
import type { LocalModelTier } from "@/lib/product/ai-preferences";
import type { AiProcessingMode } from "@/lib/product/ai-preferences";

interface ProductSettingsContextValue {
  settings: ProductSettings | null;
  source: SettingsSource | null;
  readiness: ProductReadiness | null;
  loading: boolean;
  setFocusCourseIds: (ids: string[], termHint: string | null) => Promise<void>;
  updateAi: (patch: {
    aiProcessingMode?: AiProcessingMode;
    localModelTier?: LocalModelTier;
    privacyCloudOptInAcknowledged?: boolean;
  }) => Promise<void>;
  refresh: () => void;
}

const ProductSettingsContext = createContext<ProductSettingsContextValue | null>(null);

export function ProductSettingsProvider({ children }: { children: React.ReactNode }) {
  const academicApi = useAcademicApi();
  const { connection, mode } = useBackendStatus();
  const productApi = useMemo(() => getProductSettingsApi(), []);
  const [loaded, setLoaded] = useState<LoadedProductSettings | null>(null);
  const [readiness, setReadiness] = useState<ProductReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [reloadToken, setReloadToken] = useState(0);

  const refresh = useCallback(() => {
    setReloadToken((t) => t + 1);
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const backendOk = mode === "mock" || connection === "connected";
        let syncProbe: { hasSync: boolean; relativeLabel?: string; status?: string } | undefined;
        let canvasOnline: boolean | undefined;
        if (backendOk && mode !== "mock") {
          try {
            const canvasStatus = await academicApi.probeCanvasConnection();
            canvasOnline =
              canvasStatus === "ready"
                ? true
                : canvasStatus === "unavailable"
                  ? false
                  : undefined;
          } catch {
            canvasOnline = undefined;
          }
          try {
            const run = await academicApi.getLatestSyncRun();
            if (run) {
              syncProbe = {
                hasSync: true,
                status: run.status,
                relativeLabel: formatRelativeTime(run.finishedAt ?? run.startedAt),
              };
            } else {
              syncProbe = { hasSync: false };
            }
          } catch {
            syncProbe = { hasSync: false };
          }
        }
        const [settings, ready] = await Promise.all([
          loadProductSettings(productApi),
          loadReadiness(productApi, { backendOk, syncProbe, canvasOnline }),
        ]);
        if (!active) return;
        setLoaded(settings);
        setReadiness(ready);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [productApi, connection, mode, academicApi, reloadToken]);

  const setFocusCourseIds = useCallback(
    async (ids: string[], termHint: string | null) => {
      setLoaded((prev) =>
        prev
          ? {
              ...prev,
              settings: {
                ...prev.settings,
                focusCourseIds: ids,
                termHint: termHint ?? prev.settings.termHint,
              },
            }
          : prev,
      );
      const next = await saveProductSettings(productApi, {
        focusCourseIds: ids,
        termHint,
      });
      setLoaded(next);
    },
    [productApi],
  );

  const updateAi = useCallback(
    async (patch: {
      aiProcessingMode?: AiProcessingMode;
      localModelTier?: LocalModelTier;
      privacyCloudOptInAcknowledged?: boolean;
    }) => {
      const next = await saveProductSettings(productApi, patch);
      setLoaded(next);
    },
    [productApi],
  );

  const value = useMemo(
    () => ({
      settings: loaded?.settings ?? null,
      source: loaded?.source ?? null,
      readiness,
      loading,
      setFocusCourseIds,
      updateAi,
      refresh,
    }),
    [loaded, readiness, loading, setFocusCourseIds, updateAi, refresh],
  );

  return (
    <ProductSettingsContext.Provider value={value}>{children}</ProductSettingsContext.Provider>
  );
}

export function useProductSettings(): ProductSettingsContextValue {
  const ctx = useContext(ProductSettingsContext);
  if (!ctx) throw new Error("useProductSettings requires ProductSettingsProvider");
  return ctx;
}
