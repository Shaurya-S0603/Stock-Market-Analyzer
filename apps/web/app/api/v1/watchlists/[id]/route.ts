import { authenticatedWatchlistRequest, rejectCrossOriginMutation } from "@/lib/watchlist-auth";
type Context = { params: Promise<{ id: string }> };
export async function DELETE(request: Request, context: Context) {
  const rejection = rejectCrossOriginMutation(request);
  if (rejection) return rejection;
  const { id } = await context.params;
  if (!/^[a-fA-F0-9-]{36}$/.test(id)) return Response.json({ error: "Invalid identifier" }, { status: 400 });
  return authenticatedWatchlistRequest("/api/v1/watchlists/" + encodeURIComponent(id), "DELETE");
}
