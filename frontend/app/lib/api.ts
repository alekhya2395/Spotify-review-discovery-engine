function normalizeApiBase(raw: string): string {
  const trimmed = raw.trim().replace(/\/api\/?$/i, "").replace(/\/$/, "");
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

/** Resolve the API base URL for the current runtime. */
export function apiRoot(): string {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL;
  if (publicUrl) {
    const base = normalizeApiBase(publicUrl);
    if (base) return `${base}/api`;
  }

  // Browser fallback: same-origin proxy (local dev or when only BACKEND_URL is set server-side)
  if (typeof window !== "undefined") return "/backend-api";

  // SSR / server-side fetch
  const serverUrl = process.env.BACKEND_URL;
  if (serverUrl) {
    const base = normalizeApiBase(serverUrl);
    if (base) return `${base}/api`;
  }

  return "http://127.0.0.1:8001/api";
}

async function jget<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${apiRoot()}${path}`, { cache: "no-store" });
  } catch {
    throw new Error(
      "Cannot reach the review API. Check that the Railway backend is running and NEXT_PUBLIC_API_URL is set on Vercel."
    );
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail ? `: ${typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)}` : "";
    } catch {
      /* ignore */
    }
    throw new Error(`API ${path} failed: ${res.status}${detail}`);
  }
  return res.json();
}

async function jpost<T>(path: string, body: unknown, timeoutMs = 15000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${apiRoot()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("The analysis request timed out. Please try again.");
    }
    throw new Error(
      "Cannot reach the review API. Check NEXT_PUBLIC_API_URL on Vercel and ALLOWED_ORIGINS on Railway."
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    let detail = "";
    try {
      const errBody = await res.json();
      detail = errBody.detail ? `: ${typeof errBody.detail === "string" ? errBody.detail : JSON.stringify(errBody.detail)}` : "";
    } catch {
      /* ignore */
    }
    throw new Error(`API ${path} failed: ${res.status}${detail}`);
  }
  return res.json();
}

export type Stats = {
  total_items: number;
  discovery_related: number;
  repetition_related: number;
  avg_sentiment: number;
  avg_sentiment_score?: number;
  top_pain_category?: string;
  themes_count: number;
  sources: Record<string, number>;
  pain_categories: Record<string, number>;
  sentiment_distribution?: Record<string, number>;
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
  sentiment?: string | null;
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
  sentiments?: string[];
};

export type ChatMessage = { role: "user" | "assistant"; content: string };

export const api = {
  health: () => jget<{ status: string; data: Record<string, unknown> }>("/health"),
  stats: () => jget<Stats>("/stats"),
  themes: () => jget<ThemesPayload>("/themes"),
  report: () => jget<{ markdown: string }>("/report"),
  filters: () => jget<FilterOptions>("/insights/filters"),
  insights: (params: Record<string, string | number | boolean | undefined>) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    return jget<InsightsPage>(`/insights?${qs.toString()}`);
  },
  chat: async (question: string, history: ChatMessage[]) => {
    const prior = history.filter((m) => m.content.trim().toLowerCase() !== question.trim().toLowerCase());
    return jpost<{ answer: string; grounding_size_chars: number }>(
      "/chat",
      {
        question,
        history: prior.slice(-12),
      },
      90000
    );
  },
};
