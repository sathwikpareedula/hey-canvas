import { AcademicApiError } from "@/lib/api/errors";
import { localApiClientHeaders } from "@/lib/api/http/local-api-headers";
import { messageFromHttpErrorBody } from "@/lib/api/http/parse-api-error";

async function readResponseText(res: Response): Promise<string> {
  try {
    if (typeof res.text === "function") {
      return await res.text();
    }
    if (typeof res.json === "function") {
      const body = await res.json();
      return typeof body === "string" ? body : JSON.stringify(body);
    }
  } catch {
    return "";
  }
  return "";
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const code = res.status === 404 ? "not_found" : "http";
    const bodyText = await readResponseText(res);
    const message = messageFromHttpErrorBody(res.status, bodyText);
    throw new AcademicApiError(message, res.status, code);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new AcademicApiError("Malformed JSON response", res.status, "parse");
  }
}

export async function fetchJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json", ...localApiClientHeaders() },
    });
  } catch {
    throw new AcademicApiError("Network request failed", undefined, "network");
  }
  return parseResponse<T>(res);
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...localApiClientHeaders(),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AcademicApiError("Network request failed", undefined, "network");
  }
  return parseResponse<T>(res);
}

export async function putJson<T>(url: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...localApiClientHeaders(),
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AcademicApiError("Network request failed", undefined, "network");
  }
  return parseResponse<T>(res);
}

export async function fetchHealth(baseUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${baseUrl.replace(/\/$/, "")}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return false;
    const body = (await res.json()) as { status?: string };
    return body.status === "ok";
  } catch {
    return false;
  }
}
