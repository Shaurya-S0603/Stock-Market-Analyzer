"use client";

import { useState, type FormEvent } from "react";
import { signIn, signOut, useSession } from "next-auth/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type SavedList = { id: string; name: string; symbols: string[]; created_at: string };
type ListResult = { watchlists: SavedList[] };

async function request<T>(path: string, method = "GET", payload?: object): Promise<T> {
  const response = await fetch(path, {
    method, cache: "no-store",
    headers: payload ? { "content-type": "application/json" } : undefined,
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({})) as {detail?: string; error?: string};
    throw new Error(detail.detail || detail.error || "Request failed (" + response.status + ")");
  }
  return response.json() as Promise<T>;
}

export function Watchlists() {
  const { status, data: session } = useSession();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [draftSymbols, setDraftSymbols] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const lists = useQuery({
    queryKey: ["saved-watchlists"],
    queryFn: () => request<ListResult>("/api/v1/watchlists"),
    enabled: status === "authenticated",
    retry: false,
  });
  const create = useMutation({
    mutationFn: (value: string) => request("/api/v1/watchlists", "POST", { name: value }),
    onSuccess: async () => {
      setName(""); setMessage("Watchlist created.");
      await queryClient.invalidateQueries({ queryKey: ["saved-watchlists"] });
    },
  });
  const add = useMutation({
    mutationFn: ({ id, symbol }: { id: string; symbol: string }) =>
      request("/api/v1/watchlists/" + encodeURIComponent(id) + "/symbols", "POST", { symbol }),
    onSuccess: async (_, item) => {
      setDraftSymbols(state => ({ ...state, [item.id]: "" }));
      setMessage("Ticker saved.");
      await queryClient.invalidateQueries({ queryKey: ["saved-watchlists"] });
    },
  });
  const remove = useMutation({
    mutationFn: ({ id, symbol }: { id: string; symbol?: string }) =>
      request("/api/v1/watchlists/" + encodeURIComponent(id) +
        (symbol ? "/symbols/" + encodeURIComponent(symbol) : ""), "DELETE"),
    onSuccess: async () => {
      setMessage("Saved research updated.");
      await queryClient.invalidateQueries({ queryKey: ["saved-watchlists"] });
    },
  });
  const error = create.error || add.error || remove.error || lists.error;
  function submitName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setMessage("");
    if (name.trim()) create.mutate(name.trim());
  }
  function submitSymbol(event: FormEvent<HTMLFormElement>, id: string) {
    event.preventDefault(); setMessage("");
    const symbol = (draftSymbols[id] ?? "").trim().toUpperCase();
    if (/^[A-Z0-9][A-Z0-9.^=-]{0,39}$/.test(symbol)) add.mutate({ id, symbol });
  }
  return <div className="space-y-7">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="label">Phase 1B · private saved research</p>
        <h1 className="mt-2 text-3xl font-bold">My watchlists</h1>
        <p className="mt-3 max-w-2xl text-slate-400">
          Private lists of tickers stored in PostgreSQL. Saving a ticker does not
          execute or recommend a trade and does not subscribe to live prices.
        </p>
      </div>
      {status === "authenticated" && <button type="button" onClick={() => signOut()}
        className="pill text-sm">Sign out</button>}
    </header>
    {status === "loading" && <p role="status">Checking your sign-in session…</p>}
    {status === "unauthenticated" && <section className="panel max-w-xl space-y-4 p-6">
      <h2 className="text-xl font-semibold">Sign in to save watchlists</h2>
      <p className="text-sm text-slate-400">
        This feature requires a configured GitHub OAuth app and separate
        server-side research credentials. Anonymous storage is disabled.
      </p>
      <button type="button" onClick={() => signIn("github", { callbackUrl: "/watchlists" })}
        className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500">
        Continue with GitHub
      </button>
    </section>}
    {status === "authenticated" && <>
      <p className="text-sm text-slate-400">
        Signed in as {session?.user?.name ?? "GitHub account"}. Each account sees only its own lists.
      </p>
      <form className="panel flex flex-wrap items-end gap-3 p-5" onSubmit={submitName}>
        <label className="flex flex-col gap-2 text-sm">New watchlist
          <input aria-label="New watchlist name" value={name} maxLength={64}
            onChange={event => setName(event.target.value)}
            placeholder="e.g. Research candidates" required
            className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-3" />
        </label>
        <button type="submit" disabled={create.isPending}
          className="rounded-lg bg-blue-600 px-5 py-3 font-semibold hover:bg-blue-500">
          Create watchlist
        </button>
      </form>
      {lists.isPending && <p role="status">Loading saved lists…</p>}
      {lists.data && lists.data.watchlists.length === 0 &&
        <p className="text-slate-400">No saved lists yet. Create a watchlist to begin.</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {lists.data?.watchlists.map(list => <section className="panel space-y-4 p-5" key={list.id}>
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-lg font-semibold">{list.name}</h2>
            <button type="button" className="pill text-xs text-rose-200"
              disabled={remove.isPending}
              onClick={() => {
                if (window.confirm("Delete this saved watchlist?")) remove.mutate({id:list.id});
              }}>Delete list</button>
          </div>
          <div className="flex flex-wrap gap-2">
            {list.symbols.length === 0 && <p className="text-sm text-slate-400">No tickers yet.</p>}
            {list.symbols.map(symbol => <span key={symbol}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm">
              {symbol}
              <button type="button" disabled={remove.isPending}
                aria-label={"Remove " + symbol + " from " + list.name}
                onClick={() => remove.mutate({id: list.id, symbol})}
                className="text-slate-400 hover:text-rose-200">×</button>
            </span>)}
          </div>
          <form onSubmit={event => submitSymbol(event, list.id)} className="flex flex-wrap gap-2">
            <input aria-label={"Add ticker to " + list.name}
              value={draftSymbols[list.id] ?? ""} maxLength={40}
              onChange={event => setDraftSymbols(s => ({...s, [list.id]:event.target.value}))}
              placeholder="e.g. MSFT" required
              className="w-40 rounded-lg border border-slate-600 bg-slate-950 px-3 py-2" />
            <button type="submit" disabled={add.isPending} className="pill text-sm">Add ticker</button>
          </form>
        </section>)}
      </div>
    </>}
    {message && <p className="text-emerald-300" role="status">{message}</p>}
    {error && <p className="text-rose-300" role="alert">{error.message}</p>}
    <p className="text-xs text-slate-500">
      No brokerage connectivity. Authentication and saved research are distinct
      from the optional historical market-data adapter.
    </p>
  </div>;
}
