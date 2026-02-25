"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, MessageCircleQuestion, Send, X } from "lucide-react";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

function generateAssistantReply(input: string) {
  const q = input.toLowerCase();

  if (q.includes("job") || q.includes("jenkins")) {
    return "To analyze logs, choose a Jenkins job (or enter Job ID manually), fill credentials if needed, then click Analyze Latest Jenkins Build.";
  }

  if (q.includes("email") || q.includes("schedule")) {
    return "Use Schedule Email Report to send immediately or set hourly/daily/weekly/monthly frequency.";
  }

  if (q.includes("error") || q.includes("failed")) {
    return "Please share the exact error text shown in the form alert, and I can guide the fix step-by-step.";
  }

  return "I’m your AI support assistant. Ask me about Jenkins analysis, scheduling reports, or troubleshooting this dashboard.";
}

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

    await new Promise((resolve) => setTimeout(resolve, 550));

    const reply: ChatMessage = {
      id: `a-${Date.now()}`,
      role: "assistant",
      content: generateAssistantReply(userText),
    };

    setMessages((prev) => [...prev, reply]);
    setSending(false);
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
            <div>
              <p className="text-sm font-semibold">Support AI Agent</p>
              <p className="text-xs text-white/90">Live assistant</p>
            </div>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3 dark:bg-slate-950">
            {messages.map((m) => (
              <div
                key={m.id}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[85%] rounded-xl bg-hpe-green-500 px-3 py-2 text-sm text-white"
                    : "max-w-[85%] rounded-xl bg-white px-3 py-2 text-sm text-slate-800 shadow-sm dark:bg-slate-800 dark:text-slate-100"
                }
              >
                {m.content}
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
