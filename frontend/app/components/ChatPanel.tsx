"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type ChatMessage } from "../lib/api";
import { getFallbackAnswer } from "../lib/fallback-answers";

type Props = {
  reviewCount?: number;
  pendingQuestion?: string;
  onPendingQuestionConsumed?: () => void;
};

export function ChatPanel({ pendingQuestion, onPendingQuestionConsumed }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const lastPending = useRef<string | null>(null);

  const send = async (q?: string) => {
    const question = (q ?? input).trim();
    if (!question || loading) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const { answer } = await api.chat(question, messages);
      setMessages([...next, { role: "assistant", content: answer }]);
    } catch {
      const fallback = getFallbackAnswer(question);
      setMessages([...next, { role: "assistant", content: fallback }]);
    } finally {
      setLoading(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  };

  useEffect(() => {
    const q = pendingQuestion?.trim();
    if (!q || loading || q === lastPending.current) return;
    lastPending.current = q;
    void send(q);
    onPendingQuestionConsumed?.();
  }, [pendingQuestion]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="bg-app-panel border border-app-border rounded-lg flex flex-col min-h-[640px]">
      <div className="px-5 py-4 border-b border-app-border flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-app-green" />
        <h3 className="text-sm font-semibold text-white">Review Discovery Engine</h3>
        <span className="ml-auto text-xs text-app-muted">AI-powered insights from user reviews</span>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-app-muted max-w-2xl">
            Ask any question about Spotify user feedback — discovery challenges, recommendation issues,
            listening patterns, user segments, or unmet needs. Each answer includes a summary,
            key pain points, product focus areas, and recommended actions.
          </p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-xl px-4 py-3 ${
                m.role === "user"
                  ? "bg-app-green text-black font-medium"
                  : "bg-app-bg border border-app-border"
              }`}
            >
              {m.role === "user" ? (
                <p className="text-sm whitespace-pre-wrap">{m.content}</p>
              ) : (
                <div className="markdown text-sm">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-app-bg border border-app-border rounded-xl px-4 py-3">
              <div className="flex gap-1.5">
                <Dot delay={0} />
                <Dot delay={150} />
                <Dot delay={300} />
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="p-3 border-t border-app-border flex gap-2"
      >
        <input
          type="text"
          placeholder="Ask about pain points, segments, discovery, unmet needs…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-app-bg border border-app-border rounded-lg px-4 py-2 text-sm text-app-text focus:outline-none focus:border-app-green"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-app-green hover:bg-app-green/90 disabled:opacity-40 text-black font-medium px-4 py-2 rounded-lg flex items-center gap-2 text-sm"
        >
          <Send className="w-4 h-4" />
          Send
        </button>
      </form>
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="w-1.5 h-1.5 bg-app-green rounded-full animate-pulse"
      style={{ animationDelay: `${delay}ms` }}
    />
  );
}
