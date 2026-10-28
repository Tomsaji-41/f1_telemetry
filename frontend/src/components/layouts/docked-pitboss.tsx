"use client";

import React, { useState, useEffect } from "react";
import { X, MessageSquare, Maximize2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ChatThread from "@/components/ChatThread";
import en from "@/content/en.json";
import { brand } from "@/config/brand";

export function DockedPitBoss(): React.JSX.Element | null {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);

  // All hooks must run unconditionally before any early return
  // Toggle on key 'p' or 'P' (ignoring when user is typing in input/textarea)
  useEffect(() => {
    // Don't attach keyboard handler when on full pit-boss page
    if (pathname === "/pit-boss") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName.toLowerCase();
      if (activeTag === "input" || activeTag === "textarea" || (document.activeElement as HTMLElement)?.isContentEditable) {
        return;
      }
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, pathname]);

  // If already on full pit-boss page, do not mount docked shell
  // (early return AFTER all hooks)
  if (pathname === "/pit-boss") {
    return null;
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-30 flex items-center gap-2 px-3.5 py-2.5 bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent)] text-[var(--text)] rounded-full shadow-lg transition-all"
        title="Open Pit Boss (Key P)"
      >
        <MessageSquare className="w-4 h-4 text-[var(--accent)]" />
        <span className="text-[13px] font-semibold">{en.pitboss.title}</span>
        <kbd className="px-1.5 py-0.5 bg-[var(--raised)] border border-[var(--border)] rounded text-[10px] font-mono text-[var(--text-3)]">
          P
        </kbd>
      </button>
    );
  }

  return (
    <aside
      className="fixed top-14 right-0 bottom-0 w-full sm:w-[460px] bg-[var(--surface)] border-l border-[var(--border)] z-40 shadow-2xl flex flex-col"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3.5 border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[var(--positive)]" />
          <h2 className="text-[14px] font-semibold text-[var(--text)]">{en.pitboss.title}</h2>
          <span className="text-[11px] font-mono text-[var(--text-3)]">Docked</span>
        </div>
        <div className="flex items-center gap-1">
          <Link
            href="/pit-boss"
            className="p-1.5 text-[var(--text-3)] hover:text-[var(--text)] rounded"
            title="Open full page"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </Link>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="p-1.5 text-[var(--text-3)] hover:text-[var(--text)] rounded"
            aria-label={en.common.close}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Embedded Chat Thread */}
      <div className="flex-1 overflow-hidden p-2">
        <ChatThread hideHeader />
      </div>
    </aside>
  );
}
