"use client";

import { ArrowRight, Database, MessageSquare, Sparkles, Brain } from "lucide-react";

const stages = [
  {
    icon: Database,
    title: "1. COLLECT",
    tools: "google-play-scraper · app-store-web-scraper · PRAW",
    body: "Pulls ~3,000 Spotify reviews from Play Store (IN+US), App Store (IN/US/GB), Reddit, and community forums.",
  },
  {
    icon: Brain,
    title: "2. ANALYZE",
    tools: "Groq (llama-3.3-70b) · structured JSON prompt",
    body: "Per-review extraction in batches — pain category, segment signals, sentiment, verbatim quote, unmet need.",
  },
  {
    icon: Sparkles,
    title: "3. SYNTHESIZE",
    tools: "BERTopic clustering · Groq labeling",
    body: "Clusters into 80+ themes with frequency, severity, root cause. Generates evidence-backed markdown report.",
  },
  {
    icon: MessageSquare,
    title: "4. DELIVER",
    tools: "FastAPI · Next.js · Vercel + Railway",
    body: "This dashboard — explore themes, filter reviews, search insights, chat with the data via Groq.",
  },
];

export function WorkflowDiagram() {
  return (
    <div className="space-y-6">
      <div className="bg-app-panel border border-app-border rounded-lg p-6">
        <h2 className="text-xl font-bold text-white mb-1">
          End-to-end pipeline: collect, analyze, cluster, and deliver review intelligence
        </h2>
        <p className="text-sm text-app-muted">
          Raw feedback from app stores, forums, and social sources is transformed into searchable insights.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-stretch">
        {stages.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={s.title} className="relative bg-app-panel border border-app-border rounded-lg p-5">
              <div className="w-10 h-10 rounded-lg bg-app-green/15 text-app-green flex items-center justify-center mb-3">
                <Icon className="w-5 h-5" />
              </div>
              <div className="text-xs font-bold text-app-green tracking-wider mb-1">{s.title}</div>
              <div className="text-sm text-white font-semibold mb-2">{s.tools}</div>
              <p className="text-sm text-app-muted leading-relaxed">{s.body}</p>
              {i < stages.length - 1 && (
                <ArrowRight className="hidden md:block absolute -right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-app-green bg-app-bg rounded-full p-0.5" />
              )}
            </div>
          );
        })}
      </div>

      <div className="bg-app-panel border border-app-border rounded-lg p-6">
        <h3 className="text-base font-semibold text-white mb-3">Why this is AI-native (not just AI-assisted)</h3>
        <ul className="space-y-2 text-sm text-app-text">
          <li className="flex gap-3">
            <span className="text-app-green">▸</span>
            Traditional NLP needs hand-labeled training data — this works zero-shot on any product or domain.
          </li>
          <li className="flex gap-3">
            <span className="text-app-green">▸</span>
            LLM extracts <em>intent</em> and <em>unmet need</em>, not just keywords or sentiment polarity.
          </li>
          <li className="flex gap-3">
            <span className="text-app-green">▸</span>
            Grounded chat layer turns indexed reviews into instant, queryable analysis.
          </li>
          <li className="flex gap-3">
            <span className="text-app-green">▸</span>
            All prompts are versioned in{" "}
            <code className="bg-app-bg px-1.5 py-0.5 rounded text-xs">analyzer/prompts.py</code> — fully
            auditable.
          </li>
        </ul>
      </div>
    </div>
  );
}
