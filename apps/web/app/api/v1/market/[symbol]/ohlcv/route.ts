import { backendJson, forwardJson } from "@/lib/api";
type Context = { params: Promise<{ symbol: string }> };
export async function GET(_request: Request, context: Context) {
  const { symbol } = await context.params;
  if (!/^[A-Za-z0-9.^=-]{1,40}$/.test(symbol)) {
    return Response.json({ error: "Invalid symbol" }, { status: 400 });
  }
  const path = "/api/v1/market/" + encodeURIComponent(symbol.toUpperCase()) + "/ohlcv";
  return forwardJson(await backendJson(path));
}
