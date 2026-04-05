"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, MessageCircleQuestion, Send, X, Wrench } from "lucide-react";
import { getSupportChatReply, type ToolUsed } from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolsUsed?: ToolUsed[];
};

export function SupportChatWidget() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I’m your support AI agent. How can I help with Jenkins Log Analyzer today?",
    },
  ]);

  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, open]);

  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);

  const handleSend = async () => {
    if (!canSend) return;

    const userText = input.trim();
    setInput("");

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: userText,
    };

    setMessages((prev) => [...prev, userMsg]);
    setSending(true);

    try {
      // Build conversation history from previous messages (skip welcome)
      const history = [...messages, userMsg]
        .filter((m) => m.id !== "welcome")
        .map((m) => ({ role: m.role, content: m.content }));

      const response = await getSupportChatReply(
        userText,
        { source: "support-widget" },
        history
      );

      const reply: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content: response.response,
        toolsUsed: response.tools_used,
      };

      setMessages((prev) => [...prev, reply]);
    } catch (error) {
      const fallback: ChatMessage = {
        id: `a-${Date.now()}`,
        role: "assistant",
        content:
          error instanceof Error
            ? `Support service is currently unavailable: ${error.message}`
            : "Support service is currently unavailable.",
      };
      setMessages((prev) => [...prev, fallback]);
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Open support chat"
        className="fixed right-5 bottom-5 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-hpe-green-500 text-white shadow-lg transition hover:opacity-90"
      >
        {open ? <X className="h-6 w-6" /> : <MessageCircleQuestion className="h-6 w-6" />}
      </button>

      {open ? (
        <section className="fixed right-5 bottom-22 z-50 flex h-[500px] w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-slate-300 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
          <header className="flex items-center gap-2 bg-[linear-gradient(90deg,#0B0F10_0%,#00B388_100%)] px-4 py-3 text-white">
            <Bot className="h-5 w-5" />
            <p className="text-sm font-semibold">Support Agent</p>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3 dark:bg-slate-950">
            {messages.map((m) => (
              <div key={m.id}>
                {/* Tool usage indicator */}
                {m.role === "assistant" && m.toolsUsed && m.toolsUsed.length > 0 ? (
                  <div className="mb-1 max-w-[85%] rounded-lg bg-purple-50 px-2.5 py-1.5 text-[11px] text-purple-700 dark:bg-purple-950/30 dark:text-purple-300">
                    <div className="flex items-center gap-1 font-medium">
                      <Wrench className="h-3 w-3" />
                      Used {m.toolsUsed.length} tool{m.toolsUsed.length > 1 ? "s" : ""}:
                    </div>
                    {m.toolsUsed.map((tool, i) => (
                      <div key={i} className="ml-4 mt-0.5">
                        • {tool.tool.replace(/_/g, " ")}
                      </div>
                    ))}
                  </div>
                ) : null}

                <div
                  className={
                    m.role === "user"
                      ? "ml-auto max-w-[85%] rounded-xl bg-hpe-green-500 px-3 py-2 text-sm text-white"
                      : "max-w-[85%] rounded-xl bg-white px-3 py-2 text-sm text-slate-800 shadow-sm dark:bg-slate-800 dark:text-slate-100"
                  }
                >
                {m.role === "assistant" ? (
                  <div className="space-y-1.5 [&>p]:leading-relaxed">
                    {m.content.split("\n").filter(Boolean).map((line, i) => {
                      const trimmed = line.trim();
                      const isBullet = /^[\-•\*]\s/.test(trimmed);
                      const isNumbered = /^\d+[\.\)]\s/.test(trimmed);
                      if (isBullet) {
                        return (
                          <div key={i} className="flex gap-1.5 pl-1">
                            <span className="mt-0.5 text-hpe-green-400">•</span>
                            <span>{trimmed.replace(/^[\-•\*]\s/, "")}</span>
                          </div>
                        );
                      }
                      if (isNumbered) {
                        const num = trimmed.match(/^(\d+)[\.)]/)?.[1];
                        return (
                          <div key={i} className="flex gap-1.5 pl-1">
                            <span className="font-semibold text-hpe-green-400 min-w-[1.1rem]">{num}.</span>
                            <span>{trimmed.replace(/^\d+[\.\)]\s/, "")}</span>
                          </div>
                        );
                      }
                      return <p key={i}>{trimmed}</p>;
                    })}
                  </div>
                ) : (
                  m.content
                )}
              </div>
              </div>
            ))}
            {sending ? (
              <div className="max-w-[85%] rounded-xl bg-white px-3 py-2 text-sm text-slate-500 shadow-sm dark:bg-slate-800 dark:text-slate-300">
                Thinking...
              </div>
            ) : null}
            <div ref={endRef} />
          </div>

          <div className="border-t border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask support..."
                className="h-10 flex-1 rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-emerald-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              />
              <button
                type="button"
                onClick={handleSend}
                disabled={!canSend}
                className="flex h-10 w-10 items-center justify-center rounded-md bg-hpe-green-500 text-white disabled:opacity-50"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </>
  );
}
