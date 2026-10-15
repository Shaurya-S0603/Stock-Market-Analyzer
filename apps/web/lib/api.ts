/** Same-origin Next.js backend-for-frontend. No browser access to API secrets. */
const internalUrl = process.env.FASTAPI_INTERNAL_URL ?? "http://127.0.0.1:8000";

export async function backendJson(path: string, init: RequestInit = {}): Promise<Response> {
  if (!path.startsWith("/api/v1/")) throw new Error("Unsupported upstream path");
  try {
    return await fetch(internalUrl + path, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
      headers: { "accept": "application/json", ...init.headers },
    });
  } catch {
    return Response.json({ error: "FastAPI research service is unavailable" }, { status: 503 });
  }
}

export async function forwardJson(response: Response): Promise<Response> {
  return new Response(await response.text(), {
    status: response.status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
