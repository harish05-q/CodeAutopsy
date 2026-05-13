import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "CodeAutopsy — AI-Powered Code Analysis",
  description:
    "Autonomous architecture reverse-engineering platform. Analyze GitHub repositories to generate architecture docs, dependency maps, call graphs, risk analysis, and PDF autopsy reports.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body style={{ fontFamily: "var(--font-inter), sans-serif" }}>
        {/* Top Navigation */}
        <nav
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 32px",
            background: "rgba(10, 10, 15, 0.8)",
            backdropFilter: "blur(16px)",
            borderBottom: "1px solid var(--border-default)",
          }}
        >
          <a
            href="/"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              textDecoration: "none",
            }}
          >
            <span style={{ fontSize: "1.5rem" }}>🔬</span>
            <span
              className="gradient-text"
              style={{ fontSize: "1.15rem", fontWeight: 700, letterSpacing: "-0.02em" }}
            >
              CodeAutopsy
            </span>
          </a>
          <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
            <a
              href="/"
              style={{
                color: "var(--text-secondary)",
                textDecoration: "none",
                fontSize: "0.9rem",
                transition: "color 0.2s",
              }}
            >
              Dashboard
            </a>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: "var(--text-secondary)",
                textDecoration: "none",
                fontSize: "0.9rem",
              }}
            >
              API Docs
            </a>
          </div>
        </nav>

        {/* Main Content */}
        <main style={{ paddingTop: "64px", minHeight: "100vh" }}>
          {children}
        </main>
      </body>
    </html>
  );
}
