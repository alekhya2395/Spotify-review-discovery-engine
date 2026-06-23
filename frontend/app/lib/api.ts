const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function jget<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

async function jpost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json();
}

export type Stats = {
  total_items: number;
  discovery_related: number;
  repetition_related: number;
  avg_sentiment: number;
  themes_count: number;
  sources: Record<string, number>;
  pain_categories: Record<string, number>;
};

export type Theme = {
  theme_id: string;
  theme_name: string;
  one_line_summary: string;
  estimated_frequency_pct: number;
  dominant_segment: string;
  severity: number;
  representative_quotes: string[];
  root_cause_hypothesis: string;
  what_users_want_instead: string;
};

export type ThemesPayload = {
  themes: Theme[];
  segment_breakdown: Record<string, Record<string, number> | number>;
};

export type Insight = {
  review_id: string;
  source: string;
  country?: string | null;
  rating?: number | null;
  pain_category?: string | null;
  specific_pain?: string | null;
  verbatim_quote?: string | null;
  sentiment_intensity?: number | null;
  geography?: string | null;
  language_preference?: string | null;
  listening_style?: string | null;
  unmet_need?: string | null;
  user_suggested_fix?: string | null;
  url?: string | null;
};

export type InsightsPage = {
  items: Insight[];
  total: number;
  page: number;
  page_size: number;
};

export type FilterOptions = {
  pain_categories?: string[];
  geographies?: string[];
  listening_styles?: string[];
  language_preferences?: string[];
  sources?: string[];
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export const api = {
  stats: () => jget<Stats>("/api/stats"),
  themes: () => jget<ThemesPayload>("/api/themes"),
  report: () => jget<{ markdown: string }>("/api/report"),
  filters: () => jget<FilterOptions>("/api/insights/filters"),
  insights: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    return jget<InsightsPage>(`/api/insights?${qs.toString()}`);
  },
  chat: (question: string, history: ChatMessage[]) =>
    jpost<{ answer: string; grounding_size_chars: number }>("/api/chat", { question, history }),
};
