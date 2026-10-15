import { authenticatedWatchlistRequest, rejectCrossOriginMutation } from "@/lib/watchlist-auth";
type Context = { params: Promise<{ id: string; symbol: string }> };
export async function DELETE(request: Request, context: Context) {
  const rejection = rejectCrossOriginMutation(request);
  if (rejection) return rejection;
  const { id, symbol } = await context.params;
  if (!/^[a-fA-F0-9-]{36}$/.test(id) || !/^[A-Za-z0-9.^=-]{1,40}$/.test(symbol)) {
    return Response.json({ error: "Invalid identifier or ticker" }, { status: 400 });
  }
  return authenticatedWatchlistRequest("/api/v1/watchlists/" + encodeURIComponent(id) +
    "/symbols/" + encodeURIComponent(symbol.toUpperCase()), "DELETE");
}
