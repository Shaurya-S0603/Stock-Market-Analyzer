import { SessionProvider } from "next-auth/react";
import { Watchlists } from "@/components/watchlists";

export default function WatchlistsPage() {
  return <SessionProvider><Watchlists /></SessionProvider>;
}
