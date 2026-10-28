import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import "@/styles/tokens.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { Navbar } from "@/components/layouts/navbar";
import { Sidebar } from "@/components/layouts/sidebar";
import { AppFooter } from "@/components/layouts/Footer";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-num",
  display: "swap",
});

import React, { Suspense } from "react";
import { InspectorProvider } from "@/components/layouts/inspector-drawer";
import { DockedPitBoss } from "@/components/layouts/docked-pitboss";
import { ChatProvider } from "@/components/providers/chat-provider";

export const metadata: Metadata = {
  title: "Telemetra | Formula 1 Telemetry & Strategy",
  description: "Grounded Formula 1 telemetry, race strategy, and engineering analytics.",
  icons: {
    icon: "/brand/icon-32.png",
    shortcut: "/favicon.ico",
    apple: "/brand/icon-192.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.JSX.Element {
  const buildStamp = process.env.NEXT_PUBLIC_BUILD_STAMP || Date.now().toString();
  console.log(`[Telemetra Server] process.cwd(): ${process.cwd()} | buildStamp: ${buildStamp}`);

  return (
    <html
      lang="en"
      data-theme="dark"
      data-build={buildStamp}
      className={`${ibmPlexSans.variable} ${ibmPlexMono.variable}`}
    >
      <body className="bg-[var(--bg)] text-[var(--text)] antialiased flex flex-col min-h-screen">
        <QueryProvider>
          <InspectorProvider>
            <Suspense fallback={null}>
              <ChatProvider>
                <Suspense fallback={<header className="h-14 w-full bg-[var(--surface)] border-b border-[var(--border)]" />}>
                  <Navbar />
                </Suspense>
                <div className="flex flex-1 flex-col md:flex-row">
                  <Sidebar />
                  <main className="flex-1 p-4 sm:p-6 max-w-[1480px] w-full mx-auto">
                    {children}
                  </main>
                </div>
                <DockedPitBoss />
                <AppFooter buildStamp={buildStamp} />
              </ChatProvider>
            </Suspense>
          </InspectorProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
