"use client";

import { useEffect, useState } from "react";
import { useAcademicApi } from "@/contexts/AcademicApiContext";
import { useBackendStatus } from "@/contexts/BackendStatusContext";
import { fetchAssistantRuntimeStatus } from "@/lib/api/http/assistant-status";
import { shouldShowDemoDataBadge } from "@/lib/demo/detect-synthetic-catalog";

export function useDemoDataBadge(): boolean {
  const api = useAcademicApi();
  const { mode, connection, checking } = useBackendStatus();
  const [show, setShow] = useState(mode === "mock");

  useEffect(() => {
    if (mode === "mock") {
      queueMicrotask(() => setShow(true));
      return;
    }
    if (checking || connection !== "connected") {
      queueMicrotask(() => setShow(false));
      return;
    }
    let active = true;
    Promise.all([api.getCourses(), fetchAssistantRuntimeStatus()])
      .then(([courses, status]) => {
        if (active) setShow(shouldShowDemoDataBadge(mode, courses, status));
      })
      .catch(() => {
        if (active) setShow(false);
      });
    return () => {
      active = false;
    };
  }, [api, mode, connection, checking]);

  return show;
}
