import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "QuantEdge v3 | Research Terminal",
  description: "A free personal stock research and historical paper-testing workspace.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen lg:flex">
            <aside className="border-b border-slate-800 bg-[#0b1424] px-5 py-6 lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r lg:px-6">
              <Link href="/" className="flex items-center gap-3">
                <span className="rounded-xl bg-blue-600 px-3 py-2 font-black text-white">QE</span>
                <span><strong className="block text-lg">QuantEdge</strong>
                  <span className="text-xs text-slate-400">Research Terminal v3</span>
                </span>
              </Link>
              <nav className="mt-8 flex flex-wrap gap-2 lg:flex-col" aria-label="Main navigation">
                <Link href="/" className="pill bg-slate-800 text-sm">Market & Demo</Link>
                <Link href="/roadmap" className="pill text-sm">Development roadmap</Link>
                <a href="https://github.com/Shaurya-S0603/Quant-Edge-Terminal"
                   className="pill text-sm" target="_blank" rel="noopener noreferrer">Source repository ↗</a>
              </nav>
              <p className="mt-8 max-w-sm text-xs leading-6 text-slate-400">
                Historical research and hypothetical paper simulations only.
                No live broker, portfolio funding, or trade recommendations.
              </p>
            </aside>
            <main className="min-w-0 flex-1 px-4 py-7 sm:px-8 lg:px-12 lg:py-10">
              <div className="mx-auto max-w-6xl">{children}</div>
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
