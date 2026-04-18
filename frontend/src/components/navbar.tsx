"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Boxes, Gauge, Layers, ServerCog } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Dashboard", icon: Gauge },
  { href: "/opportunities", label: "Opportunities", icon: Layers },
  { href: "/materials", label: "Materials", icon: Boxes },
  { href: "/runs", label: "Runs", icon: ServerCog },
];

export function Navbar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <Activity className="h-5 w-5 text-accent" />
          <span>Agnes</span>
          <span className="text-xs font-normal text-fg-muted">
            sourcing intelligence
          </span>
        </Link>
        <nav className="flex items-center gap-1">
          {LINKS.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-bg-muted text-fg"
                    : "text-fg-muted hover:bg-bg-muted hover:text-fg",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
