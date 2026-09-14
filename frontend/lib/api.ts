export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailMessage(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(detailMessage).join(" ");
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.msg === "string") return record.msg;
    return JSON.stringify(value);
  }
  return "Żądanie nie powiodło się.";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (
    init.body &&
    !(init.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  const type = response.headers.get("content-type") ?? "";
  const body = type.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body ? body.detail : body;
    throw new ApiError(response.status, detailMessage(detail));
  }
  return body as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "Wystąpił nieoczekiwany błąd.";
}
