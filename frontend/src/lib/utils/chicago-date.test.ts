/**
 * @vitest-environment node
 */
import { describe, expect, it } from "vitest";
import {
  formatChangeValue,
  formatChicagoDateTime,
  formatChicagoDateTimeRange,
  humanizeChangeFieldName,
} from "@/lib/utils/chicago-date";

describe("chicago-date", () => {
  it("formats due_at ISO strings in America/Chicago", () => {
    const formatted = formatChicagoDateTime("2026-10-01T22:00:00+00:00");
    expect(formatted).toMatch(/Oct/);
    expect(formatted).not.toContain("due_at");
  });

  it("labels deadlines with CDT during daylight saving time", () => {
    expect(formatChicagoDateTime("2026-10-16T04:00:00Z")).toBe("Oct 15, 11:00 PM CDT");
  });

  it("labels deadlines with CST outside daylight saving time", () => {
    expect(formatChicagoDateTime("2026-12-10T05:59:00Z")).toBe("Dec 9, 11:59 PM CST");
  });

  it("switches CDT to CST across the November DST boundary", () => {
    expect(formatChicagoDateTime("2026-11-01T06:30:00Z")).toBe("Nov 1, 1:30 AM CDT");
    expect(formatChicagoDateTime("2026-11-01T07:30:00Z")).toBe("Nov 1, 1:30 AM CST");
  });

  it("returns a dash for missing or invalid values without a zone label", () => {
    expect(formatChicagoDateTime(null)).toBe("—");
    expect(formatChicagoDateTime("not-a-date")).toBe("—");
  });

  it("labels the zone in change values and ranges", () => {
    expect(formatChangeValue("2026-10-16T04:00:00Z")).toBe("Oct 15, 11:00 PM CDT");
    expect(formatChicagoDateTimeRange("2026-10-16T04:00:00Z", "2026-12-10T05:59:00Z")).toBe(
      "Oct 15, 11:00 PM CDT → Dec 9, 11:59 PM CST",
    );
  });

  it("humanizes field names", () => {
    expect(humanizeChangeFieldName("due_at")).toBe("Due date");
  });

  it("formats change values for ISO fields", () => {
    const line = formatChangeValue("2026-10-02T22:00:00+00:00");
    expect(line).toMatch(/Oct/);
    expect(line).not.toContain("T22:00");
  });
});
