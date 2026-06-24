"use client";

import { Frown, Meh, RotateCcw, Smile } from "lucide-react";
import { useEffect, useState } from "react";
import { DarkFilterDropdown } from "./DarkFilterDropdown";
import { api, type FilterOptions, type Insight, type InsightsPage } from "../lib/api";
import {
  formatPainCategory,
  formatSegment,
  formatSource,
  sentimentFromIntensity,
} from "../lib/format";

type FilterState = {
  pain_category: string;
  listening_style: string;
  sentiment: string;
  source: string;
};

type Props = {
  searchQuery: string;
};

export function InsightsTable({ searchQuery }: Props) {
  const [filters, setFilters] = useState<FilterOptions>({});
  const [page, setPage] = useState<InsightsPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterValues, setFilterValues] = useState<FilterState>({
    pain_category: "",
    listening_style: "",
    sentiment: "",
    source: "",
  });
  const [pageNum, setPageNum] = useState(1);

  useEffect(() => {
    api.filters().then(setFilters).catch(() => setFilters({}));
  }, []);

  useEffect(() => {
    setPageNum(1);
  }, [searchQuery]);

  useEffect(() => {
    setLoading(true);
    api
      .insights({
        page: pageNum,
        page_size: 10,
        discovery_only: false,
        pain_category: filterValues.pain_category || undefined,
        listening_style: filterValues.listening_style || undefined,
        sentiment: filterValues.sentiment || undefined,
        source: filterValues.source || undefined,
        q: searchQuery || undefined,
      })
      .then(setPage)
      .catch(() => setPage(null))
      .finally(() => setLoading(false));
  }, [filterValues, pageNum, searchQuery]);

  const totalPages = page ? Math.max(1, Math.ceil(page.total / page.page_size)) : 1;

  const resetFilters = () => {
    setFilterValues({ pain_category: "", listening_style: "", sentiment: "", source: "" });
    setPageNum(1);
  };

  return (
    <section className="bg-app-panel border border-app-border rounded-lg flex flex-col overflow-hidden">
      <div className="p-4 border-b border-app-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-app-panel rounded-t-lg">
        <h2 className="text-lg font-semibold">Insights</h2>
        <div className="flex flex-wrap items-center gap-3">
          <DarkFilterDropdown
            label="Pain Category"
            value={filterValues.pain_category}
            options={filters.pain_categories || []}
            onChange={(v) => {
              setPageNum(1);
              setFilterValues((s) => ({ ...s, pain_category: v }));
            }}
            format={formatPainCategory}
          />
          <DarkFilterDropdown
            label="Segment"
            value={filterValues.listening_style}
            options={filters.listening_styles || []}
            onChange={(v) => {
              setPageNum(1);
              setFilterValues((s) => ({ ...s, listening_style: v }));
            }}
            format={formatSegment}
          />
          <DarkFilterDropdown
            label="Sentiment"
            value={filterValues.sentiment}
            options={filters.sentiments || ["positive", "negative", "neutral", "mixed"]}
            onChange={(v) => {
              setPageNum(1);
              setFilterValues((s) => ({ ...s, sentiment: v }));
            }}
            format={(v) => v.charAt(0).toUpperCase() + v.slice(1)}
          />
          <DarkFilterDropdown
            label="Source"
            value={filterValues.source}
            options={filters.sources || []}
            onChange={(v) => {
              setPageNum(1);
              setFilterValues((s) => ({ ...s, source: v }));
            }}
            format={formatSource}
          />
          <button
            type="button"
            onClick={resetFilters}
            className="flex items-center gap-2 px-3 py-1.5 bg-app-bg border border-app-border rounded text-sm text-app-text hover:bg-app-border transition-colors"
          >
            <RotateCcw className="w-4 h-4 stroke-2" />
            Reset
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm whitespace-nowrap">
          <thead className="text-app-text border-b border-app-border bg-app-panel">
            <tr>
              <th className="px-5 py-3 font-medium" scope="col">
                Source
              </th>
              <th className="px-5 py-3 font-medium w-1/3" scope="col">
                Review Text
              </th>
              <th className="px-5 py-3 font-medium" scope="col">
                Pain Category
              </th>
              <th className="px-5 py-3 font-medium" scope="col">
                Sentiment
              </th>
              <th className="px-5 py-3 font-medium" scope="col">
                Segment
              </th>
              <th className="px-5 py-3 font-medium" scope="col">
                Unmet Need
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-app-border">
            {(page?.items ?? []).map((row) => (
              <InsightRow key={row.review_id} row={row} />
            ))}
            {!loading && (page?.items?.length ?? 0) === 0 && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-app-muted whitespace-normal">
                  No reviews match these filters.
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-app-muted">
                  Loading…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {!loading && (page?.total ?? 0) > 0 && (
        <div className="px-4 py-3 flex items-center justify-between border-t border-app-border text-sm">
          <button
            type="button"
            onClick={() => setPageNum((n) => Math.max(1, n - 1))}
            disabled={pageNum === 1}
            className="px-3 py-1.5 rounded bg-app-bg border border-app-border hover:bg-app-border disabled:opacity-30"
          >
            ← Prev
          </button>
          <span className="text-app-muted">
            Page {pageNum} / {totalPages} · {page?.total.toLocaleString()} reviews
          </span>
          <button
            type="button"
            onClick={() => setPageNum((n) => Math.min(totalPages, n + 1))}
            disabled={pageNum >= totalPages}
            className="px-3 py-1.5 rounded bg-app-bg border border-app-border hover:bg-app-border disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      )}
    </section>
  );
}

function InsightRow({ row }: { row: Insight }) {
  const sentiment = (row.sentiment ?? sentimentFromIntensity(row.sentiment_intensity)).toLowerCase();
  const quote = row.verbatim_quote || row.specific_pain || "—";
  const need =
    row.unmet_need && row.unmet_need !== "none" ? row.unmet_need : row.user_suggested_fix || "—";

  return (
    <tr className="hover:bg-app-bg/50 transition-colors">
      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <SourceIcon source={row.source} />
          <span>{formatSource(row.source)}</span>
        </div>
      </td>
      <td className="px-5 py-4 whitespace-normal text-app-text">{quote}</td>
      <td className="px-5 py-4 text-app-text">{formatPainCategory(row.pain_category)}</td>
      <td className="px-5 py-4">
        <SentimentBadge sentiment={sentiment} />
      </td>
      <td className="px-5 py-4 text-app-text">{formatSegment(row.listening_style)}</td>
      <td className="px-5 py-4 whitespace-normal text-app-text">{need}</td>
    </tr>
  );
}

function SourceIcon({ source }: { source: string }) {
  if (source === "app_store") {
    return (
      <svg className="w-6 h-6 shrink-0" viewBox="0 0 24 24" fill="#1C96E8" aria-hidden>
        <path d="M4 2h16a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm10.74 15.6l-1.63-4.66H9.86l-1.62 4.66H6.67L11.3 4h1.42l4.63 13.6h-1.61zm-4.44-5.91h3.36l-1.68-4.8h-.02l-1.66 4.8z" />
      </svg>
    );
  }
  if (source === "play_store") {
    return (
      <svg className="w-6 h-6 shrink-0" viewBox="0 0 24 24" aria-hidden>
        <path d="M3 3v18l15-9-15-9z" fill="#4285F4" />
        <path d="M18 12l-6-3.6-9 5.4 15-1.8z" fill="#EA4335" />
        <path d="M18 12l-6 3.6-9-5.4 15 1.8z" fill="#FBBC04" />
        <path d="M3 3v18l9-5.4-9-5.4z" fill="#34A853" />
      </svg>
    );
  }
  if (source === "reddit") {
    return (
      <svg className="w-6 h-6 shrink-0" viewBox="0 0 24 24" fill="#FF4500" aria-hidden>
        <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
      </svg>
    );
  }
  if (source === "social_media") {
    return (
      <svg className="w-6 h-6 shrink-0" viewBox="0 0 24 24" fill="#1DA1F2" aria-hidden>
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    );
  }
  if (source === "community_forum") {
    return (
      <svg className="w-6 h-6 text-app-green stroke-2 fill-none shrink-0" viewBox="0 0 24 24" aria-hidden>
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      </svg>
    );
  }
  return (
    <svg
      className="w-6 h-6 text-app-muted stroke-2 fill-none shrink-0"
      viewBox="0 0 24 24"
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="2" x2="22" y1="12" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string }) {
  const styles: Record<string, string> = {
    positive: "border-sentiment-positive text-sentiment-positive bg-sentiment-positive/10",
    negative: "border-sentiment-negative text-sentiment-negative bg-sentiment-negative/10",
    neutral: "border-sentiment-neutral text-sentiment-neutral bg-sentiment-neutral/10",
    mixed: "border-sentiment-mixed text-sentiment-mixed bg-sentiment-mixed/10",
  };
  const label = sentiment.charAt(0).toUpperCase() + sentiment.slice(1);
  const Icon = sentiment === "positive" ? Smile : sentiment === "negative" ? Frown : Meh;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-medium ${
        styles[sentiment] ?? styles.neutral
      }`}
    >
      <Icon className="w-3.5 h-3.5 stroke-2" />
      {label}
    </span>
  );
}
