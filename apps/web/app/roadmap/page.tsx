const stages = [
  ["0", "Foundation", "Next.js, FastAPI, CI and browser-to-API connectivity", "In progress"],
  ["1", "Market data", "Provider adapters, authenticated watchlists, PostgreSQL persistence", "Planned"],
  ["2", "Chart laboratory", "Full indicator configuration and saved Lightweight Charts layouts", "Planned"],
  ["3", "Strategy lab", "Validated visual rule editor and durable cost-aware backtests", "Planned"],
  ["4", "Paper & alerts", "Per-user simulated portfolios, audit trail and scheduled alerts", "Planned"],
  ["5", "Research & deployment", "Fundamentals, screeners, accessibility, monitoring and release", "Planned"],
];
export default function Roadmap() {
  return <div className="space-y-6">
    <div><p className="label">Phased rebuild</p>
      <h1 className="mt-2 text-3xl font-bold">The QuantEdge roadmap</h1>
      <p className="mt-3 max-w-2xl text-slate-400">The Streamlit v2.1.1 release stays intact while
      each new full-stack phase is built and verified. No unfinished module is presented as deployed.</p>
    </div>
    {stages.map(([number, title, description, status]) =>
      <div className="panel flex flex-col gap-3 p-5 sm:flex-row sm:items-center" key={number}>
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-950 text-lg font-semibold text-blue-300">{number}</div>
        <div className="flex-1"><h2 className="font-semibold">{title}</h2>
          <p className="mt-1 text-sm text-slate-400">{description}</p></div>
        <span className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-300">{status}</span>
      </div>)}
  </div>;
}
