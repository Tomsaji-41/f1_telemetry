"use client";

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { brand } from "@/config/brand";

export interface ClarifyOption {
  label: string;
  value: any;
  action?: string;
  round?: number;
  page?: number;
}

export interface ChatMessage {
  id: string;
  turn_id?: string;
  role: "user" | "assistant" | "system";
  content?: string;
  blocks?: Array<any>;
  clarify?: {
    slot: string;
    question: string;
    options: ClarifyOption[];
    allow_text?: boolean;
    progress?: string;
    pending_state?: any;
  };
  followups?: Array<{ label: string; intent?: string; depth?: string; action?: string; value?: any }>;
  sources?: string[];
  resolved_context?: {
    grand_prix?: string;
    year?: number | string;
    [key: string]: any;
  };
  timestamp?: string;
  selectedChip?: any;
}

export interface StatusStep {
  stage: string;
  label: string;
  eta_s?: number;
}

interface ChatContextType {
  conversationId: string;
  messages: ChatMessage[];
  inputText: string;
  setInputText: (t: string) => void;
  isStreaming: boolean;
  activeStatus: StatusStep | null;
  error: string | null;
  isHistoryOpen: boolean;
  setIsHistoryOpen: (open: boolean) => void;
  savedConversations: any[];
  sendMessage: (text?: string, actionPayload?: any) => Promise<void>;
  cancelStream: () => void;
  retryLastMessage: () => void;
  startNewConversation: () => void;
  loadConversation: (id: string) => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

const STORAGE_KEY = "telemetra_conversations_v7";

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlConvId = searchParams.get("c");
  const [conversationId, setConversationId] = useState<string>(
    urlConvId || `conv_${Date.now()}`
  );

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeStatus, setActiveStatus] = useState<StatusStep | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUserPrompt, setLastUserPrompt] = useState<string>("");
  const [pendingState, setPendingState] = useState<any>(null);
  const [lastResolvedRace, setLastResolvedRace] = useState<any>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [savedConversations, setSavedConversations] = useState<any[]>([]);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Default welcome message generator (strictly ONE)
  const createWelcomeMessage = useCallback((): ChatMessage => {
    return {
      id: "welcome-root",
      role: "assistant",
      content: `Welcome to ${brand.assistantName}, your grounded race strategy workstation. Ask any question regarding classifications, telemetry, pit stop strategy, and championship history.`,
      sources: ["Jolpica", "FastF1", "OpenF1"],
    };
  }, []);

  // Initialize or sync with URL conversation ID
  useEffect(() => {
    // Load local history list
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSavedConversations(JSON.parse(raw));
    } catch {}

    // Fetch conversation from server if URL has ?c=
    if (urlConvId) {
      setConversationId(urlConvId);
      fetch(`/api/conversations`)
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          const list = data?.conversations || [];
          const matched = list.find((c: any) => c.id === urlConvId);
          if (matched && matched.messages && matched.messages.length > 0) {
            setMessages(matched.messages);
            return;
          }
          // If not on server, check local
          try {
            const raw = localStorage.getItem(STORAGE_KEY);
            const saved = raw ? JSON.parse(raw) : [];
            const loc = saved.find((c: any) => c.id === urlConvId);
            if (loc && loc.messages?.length > 0) {
              setMessages(loc.messages);
              return;
            }
          } catch {}
          setMessages([createWelcomeMessage()]);
        })
        .catch(() => {
          setMessages([createWelcomeMessage()]);
        });
    } else {
      setMessages([createWelcomeMessage()]);
    }
  }, [urlConvId, createWelcomeMessage]);

  // Persist conversation to server and localStorage
  const persistConversation = useCallback(
    (convId: string, msgs: ChatMessage[]) => {
      if (msgs.length <= 1) return; // Don't persist empty welcome
      const firstUserMsg = msgs.find((m) => m.role === "user");
      const title = firstUserMsg?.content?.slice(0, 40) || "Conversation";

      const convRecord = {
        id: convId,
        title,
        updated_at: new Date().toISOString(),
        messages: msgs,
      };

      // Save to server
      fetch("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(convRecord),
      }).catch(() => {});

      // Save to localStorage
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        const existing: any[] = raw ? JSON.parse(raw) : [];
        const idx = existing.findIndex((c) => c.id === convId);
        let next: any[];
        if (idx >= 0) {
          next = [...existing];
          next[idx] = convRecord;
        } else {
          next = [convRecord, ...existing];
        }
        setSavedConversations(next);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next.slice(0, 30)));
      } catch {}
    },
    []
  );

  // Reset starts a NEW conversation, keeps the old in history, sets new id in URL
  const startNewConversation = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    // Save current
    persistConversation(conversationId, messages);

    const newId = `conv_${Date.now()}`;
    setConversationId(newId);
    setMessages([createWelcomeMessage()]);
    setError(null);
    setActiveStatus(null);
    setPendingState(null);
    setLastResolvedRace(null);

    // Update URL query parameter without full reload
    const params = new URLSearchParams(searchParams.toString());
    params.set("c", newId);
    router.push(`${pathname}?${params.toString()}`);
  }, [conversationId, messages, searchParams, pathname, router, persistConversation, createWelcomeMessage]);

  // Load an existing conversation from history
  const loadConversation = useCallback(
    (id: string) => {
      persistConversation(conversationId, messages);
      setConversationId(id);
      setIsHistoryOpen(false);
      setError(null);

      const params = new URLSearchParams(searchParams.toString());
      params.set("c", id);
      router.push(`${pathname}?${params.toString()}`);
    },
    [conversationId, messages, searchParams, pathname, router, persistConversation]
  );

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsStreaming(false);
    setActiveStatus(null);
  }, []);

  const sendMessage = async (
    text?: string,
    actionPayload?: { action: string; value?: any; option_label?: string; option_index?: number }
  ) => {
    if (isStreaming) return;
    const cleanText = (text || "").trim();
    if (!cleanText && !actionPayload) return;

    setError(null);
    if (cleanText) setLastUserPrompt(cleanText);

    const turnId = `turn_${Date.now()}`;
    const userMsgId = `user_${Date.now()}`;
    const assistantMsgId = `asst_${Date.now()}`;

    let nextMessages = [...messages];

    if (cleanText && !actionPayload) {
      const userMsg: ChatMessage = {
        id: userMsgId,
        turn_id: turnId,
        role: "user",
        content: cleanText,
      };
      nextMessages.push(userMsg);
      setMessages(nextMessages);
      setInputText("");
    }

    // Add placeholder assistant message
    const asstMsg: ChatMessage = {
      id: assistantMsgId,
      turn_id: turnId,
      role: "assistant",
      content: "",
    };
    nextMessages.push(asstMsg);
    setMessages(nextMessages);

    setIsStreaming(true);
    setActiveStatus({ stage: "understanding", label: "Understanding" });

    const requestBody: any = {
      conversation_id: conversationId,
      turn_id: turnId,
      pending_state: pendingState,
      last_resolved_race: lastResolvedRace,
      history: nextMessages
        .filter((m) => m.role === "user" || (m.role === "assistant" && m.content))
        .map((m) => ({ role: m.role, text: m.content })),
    };

    if (actionPayload) {
      requestBody.action = actionPayload.action;
      requestBody.value = actionPayload.value;
      requestBody.option_label = actionPayload.option_label;
      requestBody.option_index = actionPayload.option_index;
    } else {
      requestBody.text = cleanText;
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error("The chat service is not running in this demo.");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("ReadableStream not supported by browser.");

      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() || "";

        for (const block of blocks) {
          if (!block.trim()) continue;
          let eventType = "message";
          let dataStr = "";

          for (const line of block.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.replace("event: ", "").trim();
            else if (line.startsWith("data: ")) dataStr = line.replace("data: ", "").trim();
          }

          if (!dataStr) continue;
          try {
            const data = JSON.parse(dataStr);

            if (eventType === "status") {
              const stage = data.stage || "fetching";
              const labelMap: Record<string, string> = {
                understanding: "Understanding",
                resolving_driver: "Resolving driver",
                fetching_jolpica: "Fetching Jolpica",
                fetching: "Fetching Jolpica",
                loading_fastf1: data.eta_s ? `Loading FastF1 (~${data.eta_s} s)` : "Loading FastF1",
                computing: "Computing",
                verifying: "Verifying",
                writing: "Writing",
              };
              setActiveStatus({
                stage,
                label: data.label || labelMap[stage] || stage,
                eta_s: data.eta_s,
              });
            } else if (eventType === "clarify") {
              setActiveStatus(null);
              setPendingState(data.pending_state);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content: data.question || "",
                        clarify: {
                          slot: data.slot || data.awaiting,
                          question: data.question || "",
                          options: data.options || [],
                          allow_text: data.allow_text,
                          progress: data.progress,
                          pending_state: data.pending_state,
                        },
                      }
                    : m
                )
              );
            } else if (eventType === "answer") {
              setActiveStatus(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        content: data.markdown || "",
                        followups: data.followups,
                        blocks: data.blocks,
                      }
                    : m
                )
              );
            } else if (eventType === "error") {
              setActiveStatus(null);
              setError(data.message || "An error occurred while answering.");
            } else if (eventType === "done") {
              setActiveStatus(null);
              if (data.last_resolved_race) {
                setLastResolvedRace(data.last_resolved_race);
              }
              setMessages((prev) => {
                const updated = prev.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        sources: data.sources || ["Jolpica"],
                        resolved_context: data.resolved_context,
                        timestamp: data.fetched_at || undefined,
                      }
                    : m
                );
                persistConversation(conversationId, updated);
                return updated;
              });
            }
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        setActiveStatus(null);
      } else {
        setError("The chat service is not running in this demo.");
        // Remove empty assistant placeholder so no blank bubbles appear
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantMsgId || (m.content && m.content.trim().length > 0))
        );
      }
    } finally {
      setIsStreaming(false);
      setActiveStatus(null);
      abortControllerRef.current = null;
    }
  };

  const retryLastMessage = () => {
    if (lastUserPrompt) {
      sendMessage(lastUserPrompt);
    }
  };

  return (
    <ChatContext.Provider
      value={{
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
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChat must be used within a ChatProvider");
  return ctx;
}

