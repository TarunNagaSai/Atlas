import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "katex/dist/katex.min.css";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Absolute base for OG/Twitter image URLs. Social scrapers require absolute
// URLs, so the relative image path from app/opengraph-image.tsx is resolved
// against this. Override with NEXT_PUBLIC_SITE_URL (e.g. for previews).
const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://atlas.avipra.com";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Atlas — Financial Research Copilot",
  description:
    "Grounded answers over your filings, contracts, and reports with an advanced RAG pipeline.",
  openGraph: {
    title: "Atlas — Financial Research Copilot",
    description:
      "Agentic RAG over your filings, contracts, and reports — with GraphRAG, hybrid search, and grounded citations.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Atlas — Financial Research Copilot",
    description:
      "Agentic RAG over your filings, contracts, and reports — with GraphRAG, hybrid search, and grounded citations.",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Lets content render under the iOS notch/home indicator when paired with
  // the safe-area padding in globals.css.
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f6f8" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1117" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
