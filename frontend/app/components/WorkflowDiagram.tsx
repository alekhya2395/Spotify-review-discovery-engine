"use client";

import { ArrowRight, Database, MessageSquare, Sparkles, Brain } from "lucide-react";

const stages = [
  {
    icon: Database,
    title: "1. COLLECT",
    tools: "google-play-scraper · app-store-web-scraper · PRAW",
    body: "Pulls 8,000+ Spotify reviews from Play Store (IN+US), App Store (IN/US/GB), and 5 subreddits with comments.",
  },
  {
    icon: Brain,
    title: "2. EXTRACT",
    tools: "Claude Sonnet 4.5 · structured JSON prompt",
    body: "Per-review extraction in batches of 10 — pain category, segment signals, sentiment, verbatim quote, unmet need.",
  },
  {
    icon: Sparkles,
    title: "3. SYNTHESIZE",
    tools: "Claude clustering + report prompts",
    body: "Clusters into 5-8 themes with frequency, severity, root cause. Generates evidence-backed markdown report.",
  },
  {
    icon: MessageSquare,
    title: "4. DEMO",
    tools: "FastAPI · Next.js · Vercel + Railway",
    body: "This dashboard — explore themes, filter reviews, chat with the data. Grounded Claude agent powers Q&A.",
  },
];

export function WorkflowDiagram() {
  return (
    <div className="space-y-6">
      <div className="bg-spotify-gray border border-spotify-border rounded-xl p-6">
        <h2 className="text-xl font-bold text-white mb-1">
          4-stage AI pipeline turns 8,000+ raw reviews into a queryable PM research assistant
        </h2>
        <p className="text-sm text-spotify-muted">
          The 1-slider for your deck. Screenshot this section.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-stretch">
        {stages.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={s.title} className="relative bg-spotify-gray border border-spotify-border rounded-xl p-5">
              <div className="w-10 h-10 rounded-lg bg-spotify-green/15 text-spotify-green flex items-center justify-center mb-3">
                <Icon className="w-5 h-5" />
              </div>
              <div className="text-xs font-bold text-spotify-green tracking-wider mb-1">{s.title}</div>
              <div className="text-sm text-white font-semibold mb-2">{s.tools}</div>
              <p className="text-sm text-spotify-muted leading-relaxed">{s.body}</p>
              {i < stages.length - 1 && (
                <ArrowRight className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-spotify-green bg-spotify-black rounded-full p-0.5" />
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-spotify-gray border border-spotify-border rounded-xl p-6">
        <h3 className="text-base font-semibold text-white mb-3">Why this is AI-native (not just AI-assisted)</h3>
        <ul className="space-y-2 text-sm text-spotify-text">
          <li className="flex gap-3">
            <span className="text-spotify-green">▸</span>
            Traditional NLP needs hand-labeled training data — this works zero-shot on any product or domain.
          </li>
          <li className="flex gap-3">
            <span className="text-spotify-green">▸</span>
            LLM extracts <em>intent</em> and <em>unmet need</em>, not just keywords or sentiment polarity.
          </li>
          <li className="flex gap-3">
            <span className="text-spotify-green">▸</span>
            Grounded chat layer turns 8,000 reviews into a queryable PM research assistant.
          </li>
          <li className="flex gap-3">
            <span className="text-spotify-green">▸</span>
            All 4 prompts are versioned in <code className="bg-spotify-black px-1.5 py-0.5 rounded text-xs">analyzer/prompts.py</code> — fully auditable.
          </li>
        </ul>
      </div>
    </div>
  );
}
