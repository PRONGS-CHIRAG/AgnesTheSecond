import type { Metadata } from "next";

import { TopNav } from "@/components/TopNav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Agnes 2 — substitution & sourcing",
  description:
    "Evidence-grounded raw-material substitution and sourcing consolidation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col bg-gradient-to-br from-slate-50 via-slate-50 to-indigo-50/40 text-slate-900 antialiased">
        <TopNav />
        <div className="flex flex-1 flex-col">{children}</div>
      </body>
    </html>
  );
}
