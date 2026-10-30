"use client";

import React, { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";
import {
  Send,
  Bot,
  User,
  History,
  RotateCcw,
  Loader2,
  ExternalLink,
  X,
  AlertCircle,
  Square,
} from "lucide-react";
import { ClarifyChips } from "./ClarifyChips";
import { useChat, ChatMessage } from "@/components/providers/chat-provider";
import { brand } from "@/config/brand";
import en from "@/content/en.json";

export { type ChatMessage } from "@/components/providers/chat-provider";

export function ChatThread({ hideHeader = false }: { hideHeader?: boolean }): React.JSX.Element {
  const {
    conversationId,
    messages,
    inputText,
    setInputText,
    isStreaming,
    activeStatus,
    error,
    isHistoryOpen,
    setIsHistoryOpen,
    savedConversations,
    sendMessage,
    cancelStream,
    retryLastMessage,
    startNewConversation,
    loadConversation,
  } = useChat();

  const threadEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeStatus]);

  const handleChipClick = (value: any, label: string, action?: string, chip?: any) => {
    sendMessage(undefined, {
      action: action || "select",
      value,
      chip,
      option_label: label,
    });
  };

  const handleCancelPending = () => {
    sendMessage(undefined, { action: "cancel" });
  };

  return (
    <div className="flex flex-col h-full border border-[var(--border)] rounded-lg bg-[var(--surface)] overflow-hidden relative">
      {/* Panel Header */}
      {!hideHeader && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-[var(--surface)]">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-[var(--positive)]" />
            <h2 className="text-[14px] font-semibold text-[var(--text)]">
              {brand.assistantName}
            </h2>
            <span className="text-[11px] font-mono text-[var(--text-3)]">
              Engineering Console
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsHistoryOpen(!isHistoryOpen)}
              className="text-[12px] text-[var(--text-3)] hover:text-[var(--text)] flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--raised)] transition-colors"
              title="Chat History"
            >
              <History className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">History</span>
            </button>

            <button
              type="button"
              onClick={startNewConversation}
              className="text-[12px] text-[var(--text-3)] hover:text-[var(--text)] flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--raised)] transition-colors"
              title="Start new conversation (keeps history)"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>
      )}

      {/* History Drawer Overlay */}
      {isHistoryOpen && (
        <div className="absolute inset-0 bg-[var(--surface)] z-20 flex flex-col p-4 border-b border-[var(--border)] animate-fadeIn">
          <div className="flex items-center justify-between pb-3 border-b border-[var(--border)]">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-[var(--accent)]" />
              <h3 className="text-[14px] font-semibold text-[var(--text)]">
                Conversation History
              </h3>
            </div>
            <button
              type="button"
              onClick={() => setIsHistoryOpen(false)}
              className="p-1 text-[var(--text-3)] hover:text-[var(--text)] rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto py-2 space-y-1">
            {savedConversations.length === 0 ? (
              <p className="text-[12px] text-[var(--text-3)] py-4 text-center">
                No archived conversations yet.
              </p>
            ) : (
              savedConversations.map((c: any) => {
                const isActive = c.id === conversationId;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => loadConversation(c.id)}
                    className={`w-full text-left p-2.5 rounded text-[12px] transition-colors flex items-center justify-between ${
                      isActive
                        ? "bg-[var(--raised)] text-[var(--text)] font-medium border border-[var(--border)]"
                        : "hover:bg-[var(--raised)] text-[var(--text-2)]"
                    }`}
                  >
                    <span className="truncate flex-1">{c.title || "Conversation"}</span>
                    <span className="text-[10px] font-mono text-[var(--text-3)] ml-2 shrink-0">
                      {c.updated_at ? new Date(c.updated_at).toLocaleDateString() : ""}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, idx) => {
          const isUser = m.role === "user";
          const isLastMsg = idx === messages.length - 1;

          return (
            <div
              key={m.id}
              className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
            >
              {!isUser && (
                <div className="w-7 h-7 rounded bg-[var(--raised)] border border-[var(--border)] flex items-center justify-center text-[var(--accent)] shrink-0 mt-0.5">
                  <Bot className="w-4 h-4" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-lg p-4 text-[13px] ${
                  isUser
                    ? "bg-[var(--accent)] text-white shadow-sm"
                    : "bg-[var(--raised)] border border-[var(--border)] text-[var(--text)]"
                }`}
                style={{ borderRadius: "var(--radius-m)" }}
              >
                {/* Progress line */}
                {m.clarify?.progress && (
                  <div className="text-[11px] font-mono text-[var(--accent)] pb-2 mb-2 border-b border-[var(--border)]">
                    {m.clarify.progress}
                  </div>
                )}

                {/* Entity Card Blocks */}
                {m.blocks?.map((block: any, bIdx: number) => {
                  if (block.type === "entity_card") {
                    return (
                      <div
                        key={bIdx}
                        className="mb-3 p-3 border border-[var(--border)] rounded bg-[var(--surface)] flex flex-col space-y-2"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-[10px] font-mono uppercase text-[var(--accent)]">
                              {block.entity_type} Profile
                            </span>
                            <h3 className="text-[15px] font-semibold text-[var(--text)]">
                              {block.name}
                            </h3>
                            <p className="text-[12px] text-[var(--text-3)]">
                              {block.team}
                            </p>
                          </div>
                          {block.position && (
                            <span className="text-[18px] font-mono font-bold text-[var(--text)]">
                              {block.position}
                            </span>
                          )}
                        </div>
                        {block.link && (
                          <Link
                            href={block.link}
                            className="text-[12px] text-[var(--accent)] hover:underline flex items-center gap-1 pt-1"
                          >
                            <span>Open telemetry profile</span>
                            <ExternalLink className="w-3 h-3" />
                          </Link>
                        )}
                      </div>
                    );
                  }
                  return null;
                })}

                {/* Markdown content */}
                {m.content && (
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  </div>
                )}

                {/* Clarification Options */}
                {m.clarify?.options && (
                  <ClarifyChips
                    options={m.clarify.options}
                    onSelect={(val, lbl, act) => handleChipClick(val, lbl, act)}
                    onCancel={handleCancelPending}
                    disabled={m.selectedChip !== undefined || isStreaming}
                    selectedValue={m.selectedChip}
                    isActiveTurn={isLastMsg}
                  />
                )}

                {/* Follow-up Action Chips */}
                {!isUser && m.followups && m.followups.length > 0 && !m.clarify && (
                  <div className="pt-3 mt-3 border-t border-[var(--border)] flex flex-wrap gap-1.5">
                    {m.followups.map((f: any, fIdx: number) => (
                      <button
                        key={fIdx}
                        type="button"
                        onClick={() => {
                          if (f.action === "chip" || f.intent || f.slots) {
                            handleChipClick(
                              f.value || { intent: f.intent, slots: f.slots },
                              f.label,
                              "chip",
                              { intent: f.intent, slots: f.slots }
                            );
                          } else {
                            handleChipClick(f.value || f.label, f.label, f.action || "select");
                          }
                        }}
                        disabled={isStreaming}
                        className="text-[11px] px-2.5 py-1 rounded border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--raised)] text-[var(--text-2)] hover:text-[var(--text)] transition-colors"
                      >
                        {f.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Footer: Sources actually used and dynamic timestamp */}
                {!isUser && !m.clarify && ((m.sources && m.sources.length > 0) || m.resolved_context?.grand_prix) && (
                  <div className="mt-3 pt-2 border-t border-[var(--border)] text-[11px] font-mono text-[var(--text-3)] flex items-center justify-between">
                    <span>
                      {m.resolved_context?.grand_prix
                        ? `Race: ${m.resolved_context.grand_prix} | `
                        : ""}
                      {m.sources && m.sources.length > 0
                        ? Array.from(new Set(m.sources)).join(", ")
                        : ""}
                    </span>
                    <span>{m.timestamp || ""}</span>
                  </div>
                )}
              </div>

              {isUser && (
                <div className="w-7 h-7 rounded bg-[var(--accent)] text-white flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {/* Live Step Status with Cancel */}
        {isStreaming && (
          <div className="flex items-center justify-between text-[12px] text-[var(--accent)] bg-[var(--raised)] border border-[var(--border)] px-3 py-1.5 rounded w-fit animate-pulse">
            <div className="flex items-center gap-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>
                {activeStatus?.label || "Processing request..."}
                {activeStatus?.eta_s ? ` (~${activeStatus.eta_s}s)` : ""}
              </span>
            </div>
            <button
              type="button"
              onClick={cancelStream}
              className="ml-3 text-[11px] text-[var(--text-3)] hover:text-[var(--negative)] flex items-center gap-1"
              title="Cancel request"
            >
              <Square className="w-3 h-3 fill-current" />
              <span>Cancel</span>
            </button>
          </div>
        )}

        {/* Visible Error Banner with Retry */}
        {error && (
          <div className="flex items-center justify-between p-3 rounded bg-[var(--negative-dim,rgba(239,68,68,0.1))] border border-[var(--negative,rgba(239,68,68,0.5))] text-[12px] text-[var(--text)]">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-[var(--negative,#ef4444)] shrink-0" />
              <span>{error}</span>
            </div>
            <button
              type="button"
              onClick={retryLastMessage}
              className="px-2.5 py-1 text-[11px] font-medium bg-[var(--surface)] hover:bg-[var(--raised)] border border-[var(--border)] rounded transition-colors text-[var(--text)]"
            >
              Retry
            </button>
          </div>
        )}

        <div ref={threadEndRef} />
      </div>

      {/* Input Form */}
      <div className="p-3 border-t border-[var(--border)] bg-[var(--surface)]">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (inputText.trim()) {
              sendMessage(inputText);
            }
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder={en.pitboss.inputPlaceholder}
            disabled={isStreaming}
            className="flex-1 px-3 py-2 text-[13px] bg-[var(--raised)] border border-[var(--border)] rounded text-[var(--text)] placeholder-[var(--text-3)] focus:outline-none focus:border-[var(--accent)]"
            style={{ borderRadius: "var(--radius-s)" }}
          />
          <button
            type="submit"
            disabled={isStreaming || !inputText.trim()}
            className="px-3.5 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white rounded transition-colors"
            style={{ borderRadius: "var(--radius-s)" }}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatThread;
