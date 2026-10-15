import { authenticatedWatchlistRequest, rejectCrossOriginMutation } from "@/lib/watchlist-auth";

export async function GET() {
  return authenticatedWatchlistRequest("/api/v1/watchlists");
}

export async function POST(request: Request) {
  const rejection = rejectCrossOriginMutation(request);
  if (rejection) return rejection;
  const body = await request.text();
  if (body.length > 2048) return Response.json({ error: "Body too large" }, { status: 413 });
  return authenticatedWatchlistRequest("/api/v1/watchlists", "POST", body);
}
