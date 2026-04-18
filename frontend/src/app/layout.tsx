import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Agnes · sourcing intelligence",
  description:
    "Evidence-grounded raw-material substitution and sourcing consolidation dashboard.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen">
        <Providers>
          <Navbar />
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
