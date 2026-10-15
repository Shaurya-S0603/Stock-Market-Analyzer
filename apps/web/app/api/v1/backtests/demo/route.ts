import { backendJson, forwardJson } from "@/lib/api";
export async function POST(request: Request) {
  const raw = await request.text();
  if (raw.length > 500) {
    return Response.json({ error: "Request too large" }, { status: 413 });
  }
  let payload: unknown;
  try { payload = JSON.parse(raw); }
  catch { return Response.json({ error: "Invalid JSON" }, { status: 400 }); }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return Response.json({ error: "Expected JSON object" }, { status: 400 });
  }
  const values = payload as Record<string, unknown>;
  if (Object.keys(values).some(key => key !== "starting_cash")) {
    return Response.json({ error: "Unsupported parameter" }, { status: 400 });
  }
  const amount = values.starting_cash ?? 10000;
  if (typeof amount !== "number" || !Number.isFinite(amount) || amount < 100 || amount > 1_000_000) {
    return Response.json({ error: "Starting cash must be 100–1,000,000" }, { status: 400 });
  }
  return forwardJson(await backendJson("/api/v1/backtests/demo", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ starting_cash: amount }),
  }));
}
