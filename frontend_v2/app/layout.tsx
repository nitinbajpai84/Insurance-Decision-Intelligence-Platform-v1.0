import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import MobileNav from "@/components/MobileNav";
import APIStatusBanner from "@/components/APIStatusBanner";

export const metadata: Metadata = {
  title: "Meridian — Insurance Decision Intelligence",
  description:
    "Meridian is an agentic decision intelligence platform for insurance: parallel context retrieval, validated DuckDB SQL, streaming insights, and full evidence tracing."
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
                  <p className="truncate text-sm font-bold text-gray-900">Meridian Decision Intelligence</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2.5 rounded-full border border-gray-200 bg-white py-1 pl-1 pr-3 shadow-sm">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-orange text-[11px] font-bold text-white">
                  NB
                </span>
                <span className="hidden text-left sm:block">
                  <span className="block text-xs font-bold leading-tight text-gray-900">Nitin Bajpai</span>
                  <span className="block text-[10px] font-semibold uppercase tracking-wide text-gray-400">Admin</span>
                </span>
              </div>
            </header>
            <APIStatusBanner />
            <main className="flex-1">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
