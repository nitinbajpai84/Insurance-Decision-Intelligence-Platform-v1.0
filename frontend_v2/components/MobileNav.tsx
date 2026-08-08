"use client";

/**
 * MobileNav — hamburger + slide-in drawer for screens below `lg`.
 *
 * The desktop Sidebar is `hidden lg:flex`, so without this there is no way to
 * navigate between pages on a phone or small tablet. Shares its links with the
 * sidebar via components/navItems.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu, ShieldCheck, X } from "lucide-react";
import { useEffect, useState } from "react";
import { NAV, PROCESS_NAV, isActive, type NavItem } from "./navItems";

export default function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Close the drawer whenever the route changes (tapping a link navigates).
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // Prevent the page behind the drawer from scrolling while it is open.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  // Escape closes the drawer.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const renderLink = (item: NavItem) => {
    const active = isActive(pathname, item.href);
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={() => setOpen(false)}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-semibold transition-colors ${
          active ? "bg-pwc-orange text-white" : "text-gray-300 hover:bg-white/10 hover:text-white"
        }`}
      >
        <Icon size={18} />
        {item.label}
      </Link>
    );
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
        aria-expanded={open}
        className="inline-flex items-center justify-center rounded-lg p-2 text-gray-600 hover:bg-gray-100 hover:text-gray-900 lg:hidden"
      >
        <Menu size={22} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            className="absolute inset-y-0 left-0 flex w-[17rem] max-w-[85%] flex-col bg-pwc-charcoal text-white shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-pwc-orange">
                  <ShieldCheck size={22} />
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-pwc-yellow">
                    Insurance PoC
                  </p>
                  <h2 className="text-base font-bold leading-tight">Intelligence · V2</h2>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close navigation menu"
                className="rounded-lg p-2 text-gray-300 hover:bg-white/10 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 thin-scroll">
              {NAV.map(renderLink)}
              <p className="px-3 pb-1 pt-4 text-[10px] font-bold uppercase tracking-[0.16em] text-gray-500">
                Business Processes
              </p>
              {PROCESS_NAV.map(renderLink)}
            </nav>
          </div>
        </div>
      )}
    </>
  );
}
