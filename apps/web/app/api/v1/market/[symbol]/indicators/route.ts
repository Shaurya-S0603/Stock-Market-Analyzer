import { backendJson, forwardJson } from "@/lib/api";
type Context = { params: Promise<{ symbol: string }> };
export async function GET(request: Request, context: Context) {
  const { symbol } = await context.params;
  if (!/^[A-Za-z0-9.^=-]{1,40}$/.test(symbol)) {
    return Response.json({ error: "Invalid symbol" }, { status: 400 });
  }
  const period = new URL(request.url).searchParams.get("period") ?? "20";
  if (!/^\d{1,3}$/.test(period) || Number(period) < 2 || Number(period) > 250) {
    return Response.json({ error: "Period must be from 2 to 250" }, { status: 400 });
  }
  const path = "/api/v1/market/" + encodeURIComponent(symbol.toUpperCase()) + "/indicators?period=" + period;
  return forwardJson(await backendJson(path));
}
