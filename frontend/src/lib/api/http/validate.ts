import { AcademicApiMalformedError } from "@/lib/api/errors";

export function expectArray<T>(value: unknown, label: string): T[] {
  if (!Array.isArray(value)) {
    throw new AcademicApiMalformedError(`${label} response was not a JSON array`);
  }
  return value as T[];
}

export function expectObject(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new AcademicApiMalformedError(`${label} response was not a JSON object`);
  }
  return value as Record<string, unknown>;
}
