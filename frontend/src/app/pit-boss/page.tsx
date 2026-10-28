"use client";

import React from "react";
import ChatThread from "@/components/ChatThread";
import en from "@/content/en.json";

export default function PitBossPage(): React.JSX.Element {
  return (
    <div className="space-y-4 max-w-4xl mx-auto h-[calc(100vh-100px)] flex flex-col">
      <div className="pb-3 border-b border-[var(--border)]">
        <h1 className="text-[28px] font-semibold tracking-tight text-[var(--text)]">
          {en.pitboss.title}
        </h1>
        <p className="text-[13px] text-[var(--text-3)] mt-0.5">
          {en.pitboss.welcome}
        </p>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatThread />
      </div>
    </div>
  );
}
