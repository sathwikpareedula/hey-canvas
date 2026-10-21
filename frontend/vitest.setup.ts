import "@testing-library/jest-dom/vitest";
import { completeOnboarding } from "./src/lib/product/onboarding";

/** Default unit test runs must not hit a live backend (shell env may set RUN_*). */
if (process.env.VITEST_INCLUDE_INTEGRATION !== "1") {
  delete process.env.RUN_PRODUCT_INTEGRATION;
  delete process.env.RUN_ASSISTANT_INTEGRATION;
}

if (typeof window !== "undefined") {
  completeOnboarding();
}
