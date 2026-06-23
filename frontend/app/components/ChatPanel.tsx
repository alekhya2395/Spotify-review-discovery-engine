"use client";

import { useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type ChatMessage } from "../lib/api";

const STARTERS = [
  "What are the top 3 discovery pain points for Indian users?",
  "Why do users fall into repetitive listening loops?",
  "Which user segment should Spotify prioritize? Justify with evidence.",
  "Suggest 2 product bets to fix the #1 discovery theme.",
];

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async (q?: string) => {
    const question = (q ?? input).trim();
    if (!question || loading) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: question }];
    setMessages(next);
    setInput("");
    setLoading(true);
    try {
      const { answer } = await api.chat(question, next);
      setMessages([...next, { role: "assistant", content: answer }]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setMessages([...next, { role: "assistant", content: `⚠ Chat failed: ${msg}` }]);
    } finally {
      setLoading(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    }
  };

  return (
    <div className="bg-spotify-gray border border-spotify-border rounded-xl flex flex-col h-[640px]">
      <div className="px-5 py-4 border-b border-spotify-border flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-spotify-green" />
        <h3 className="text-sm font-semibold text-white">Chat with your 8,000+ reviews</h3>
        <span className="ml-auto text-xs text-spotify-muted">Grounded on themes + insights</span>
      </div>

      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-4">
            <p className="text-sm text-spotify-muted">
              Ask any PM-style question. Answers are grounded on the extracted insights and themes, with verbatim quotes.
            </p>
            <div className="grid sm:grid-cols-2 gap-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left text-sm p-3 bg-spotify-black border border-spotify-border rounded-lg hover:border-spotify-green hover:text-spotify-green transition"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-3 ${
                m.role === "user"
                  ? "bg-spotify-green text-black font-medium"
                  : "bg-spotify-black border border-spotify-border"
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
            <div className="bg-spotify-black border border-spotify-border rounded-xl px-4 py-3">
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
        className="p-3 border-t border-spotify-border flex gap-2"
      >
        <input
          type="text"
          placeholder="Ask about pain points, segments, opportunities…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-spotify-black border border-spotify-border rounded-lg px-4 py-2 text-sm text-spotify-text focus:outline-none focus:border-spotify-green"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-spotify-green hover:bg-spotify-green/90 disabled:opacity-40 text-black font-medium px-4 py-2 rounded-lg flex items-center gap-2 text-sm"
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
      className="w-1.5 h-1.5 bg-spotify-green rounded-full"
      style={{
        animation: "pulse 1.2s ease-in-out infinite",
        animationDelay: `${delay}ms`,
      }}
    />
  );
}
