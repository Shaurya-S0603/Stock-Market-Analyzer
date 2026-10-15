import { backendJson, forwardJson } from "@/lib/api";
type Context = { params: Promise<{ symbol: string }> };
export async function GET(request: Request, context: Context) {
  const { symbol } = await context.params;
  if (!/^[A-Za-z0-9.^=-]{1,40}$/.test(symbol)) {
    return Response.json({ error: "Invalid symbol" }, { status: 400 });
  }
  const period = new URL(request.url).searchParams.get("period") ?? "6mo";
  const interval = new URL(request.url).searchParams.get("interval") ?? "1d";
  if (!["3mo", "6mo", "1y"].includes(period) || interval !== "1d") {
    return Response.json({ error: "Unsupported history period or interval" }, { status: 400 });
  }
  const path = "/api/v1/market/" + encodeURIComponent(symbol.toUpperCase()) +
    "/ohlcv?period=" + encodeURIComponent(period) + "&interval=1d";
  return forwardJson(await backendJson(path));
}
