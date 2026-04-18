"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV: { href: string; label: string; accent?: "brand" }[] = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/procurement", label: "Procurement" },
  { href: "/risks", label: "Risks" },
  { href: "/voicechat", label: "Agnes 2", accent: "brand" },
];

export function TopNav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-6 py-3">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-500 text-sm font-bold text-white shadow-sm">
            A
          </span>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-slate-900">Agnes 2</div>
            <div className="text-[11px] text-slate-500">
              Substitution & sourcing
            </div>
          </div>
        </Link>

        <nav>
          <ul className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            {NAV.map((l) => {
              const active =
                pathname === l.href ||
                (l.href !== "/" && pathname?.startsWith(l.href));
              const isBrand = l.accent === "brand";
              const cls = isBrand
                ? active
                  ? "bg-gradient-to-r from-indigo-600 via-violet-600 to-fuchsia-600 text-white shadow-sm"
                  : "bg-gradient-to-r from-indigo-50 to-fuchsia-50 text-indigo-700 hover:from-indigo-100 hover:to-fuchsia-100"
                : active
                  ? "bg-slate-900 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100";
              return (
                <li key={l.href}>
                  <Link
                    href={l.href}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${cls}`}
                  >
                    {isBrand && (
                      <span
                        aria-hidden
                        className={`text-xs ${
                          active ? "text-white" : "text-indigo-500"
                        }`}
                      >
                        ★
                      </span>
                    )}
                    {l.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <a
          href="http://127.0.0.1:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="hidden items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50 md:inline-flex"
        >
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
          API
        </a>
      </div>
    </header>
  );
}
