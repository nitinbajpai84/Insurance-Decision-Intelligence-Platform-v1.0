import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
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
            <header className="flex items-center justify-between gap-3 border-b border-gray-200 bg-white px-4 py-3 sm:px-6">
              <div className="flex min-w-0 items-center gap-2">
                <MobileNav />
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-gray-400">Business workspace</p>
                  <p className="truncate text-sm font-bold text-gray-900">Insurance Intelligence Product · V2</p>
                </div>
              </div>
              <span className="hidden shrink-0 rounded-full bg-pwc-orange/10 px-3 py-1 text-xs font-bold text-pwc-orange sm:inline">
                PwC theme
              </span>
            </header>
            <APIStatusBanner />
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
