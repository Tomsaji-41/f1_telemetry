"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { X, MessageSquare } from "lucide-react";
import en from "@/content/en.json";

export interface InspectorItem {
  type: "driver" | "team" | "lap" | "point" | "incident";
  title: string;
  subtitle?: string;
  details?: Record<string, any>;
  queryContext?: string;
}

interface InspectorContextType {
  inspectItem: (item: InspectorItem) => void;
  closeInspector: () => void;
  currentItem: InspectorItem | null;
  isOpen: boolean;
  openChatWithContext: (query: string) => void;
}

const InspectorContext = createContext<InspectorContextType>({
  inspectItem: () => {},
  closeInspector: () => {},
  currentItem: null,
  isOpen: false,
  openChatWithContext: () => {},
});

export function useInspector() {
  return useContext(InspectorContext);
}

export function InspectorProvider({
  children,
  onOpenChat,
}: {
  children: React.ReactNode;
  onOpenChat?: (contextQuery: string) => void;
}) {
  const [currentItem, setCurrentItem] = useState<InspectorItem | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const inspectItem = (item: InspectorItem) => {
    setCurrentItem(item);
    setIsOpen(true);
  };

  const closeInspector = () => {
    setIsOpen(false);
  };

  const openChatWithContext = (query: string) => {
    if (onOpenChat) {
      onOpenChat(query);
    }
  };

  // Close on ESC
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        closeInspector();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <InspectorContext.Provider
      value={{ inspectItem, closeInspector, currentItem, isOpen, openChatWithContext }}
    >
      {children}
      {isOpen && currentItem && (
        <aside
          className="fixed top-14 right-0 bottom-0 w-[400px] bg-[var(--surface)] border-l border-[var(--border)] z-30 shadow-2xl flex flex-col transition-transform duration-[var(--dur-2)] ease-[var(--ease)]"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
            <div>
              <span className="text-[11px] font-mono uppercase text-[var(--text-3)]">
                {currentItem.type} Inspector
              </span>
              <h2 className="text-[16px] font-semibold text-[var(--text)] mt-0.5">
                {currentItem.title}
              </h2>
              {currentItem.subtitle && (
                <p className="text-[12px] text-[var(--text-2)]">{currentItem.subtitle}</p>
              )}
            </div>
            <button
              type="button"
              onClick={closeInspector}
              className="p-1.5 text-[var(--text-3)] hover:text-[var(--text)] hover:bg-[var(--raised)] rounded"
              aria-label={en.common.close}
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {currentItem.details && (
              <div className="space-y-2">
                <h3 className="text-[12px] font-semibold text-[var(--text-3)] uppercase tracking-wider">
                  Telemetry Metrics
                </h3>
                <div className="border border-[var(--border)] rounded bg-[var(--raised)] divide-y divide-[var(--border)]">
                  {Object.entries(currentItem.details).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between px-3 py-2 text-[12px]">
                      <span className="text-[var(--text-2)]">{k}</span>
                      <span className="font-mono text-[var(--text)] font-medium">
                        {String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Action Footer */}
          <div className="p-4 border-t border-[var(--border)] bg-[var(--raised)]">
            <button
              type="button"
              onClick={() => {
                const q = currentItem.queryContext || `Tell me about ${currentItem.title}`;
                openChatWithContext(q);
              }}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-[13px] font-medium rounded transition-colors"
              style={{ borderRadius: "var(--radius-s)" }}
            >
              <MessageSquare className="w-4 h-4" />
              <span>{en.common.askPitBoss}</span>
            </button>
          </div>
        </aside>
      )}
    </InspectorContext.Provider>
  );
}
