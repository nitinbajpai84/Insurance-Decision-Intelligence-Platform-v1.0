import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import APIStatusBanner from "@/components/APIStatusBanner";

export const metadata: Metadata = {
  title: "Insurance Intelligence — V2",
  description:
    "Insurance PoC V2 — agentic decision intelligence: parallel context retrieval, validated DuckDB SQL, streaming insights, and full evidence tracing. PwC-themed."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen bg-gray-100 text-gray-900">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Business workspace</p>
                <p className="text-sm font-bold text-gray-900">Insurance Intelligence Product · V2</p>
              </div>
              <span className="rounded-full bg-pwc-orange/10 px-3 py-1 text-xs font-bold text-pwc-orange">PwC theme</span>
            </header>
            <APIStatusBanner />
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
