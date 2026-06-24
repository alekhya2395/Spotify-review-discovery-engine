"use client";

import { useEffect, useState } from "react";
import { Filter } from "lucide-react";
import { api, type FilterOptions, type Insight, type InsightsPage } from "../lib/api";

export function ReviewExplorer() {
  const [filters, setFilters] = useState<FilterOptions>({});
  const [page, setPage] = useState<InsightsPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterValues, setFilterValues] = useState({
    pain_category: "",
    geography: "",
    listening_style: "",
    source: "",
    discovery_only: true,
  });
  const [pageNum, setPageNum] = useState(1);

  useEffect(() => {
    api.filters().then(setFilters).catch(() => setFilters({}));
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .insights({
        page: pageNum,
        page_size: 10,
        pain_category: filterValues.pain_category || undefined,
        geography: filterValues.geography || undefined,
        listening_style: filterValues.listening_style || undefined,
        source: filterValues.source || undefined,
        discovery_only: filterValues.discovery_only,
      })
      .then(setPage)
      .catch(() => setPage(null))
      .finally(() => setLoading(false));
  }, [filterValues, pageNum]);

  const totalPages = page ? Math.max(1, Math.ceil(page.total / page.page_size)) : 1;

  const onFilter = (k: string, v: string | boolean) => {
    setPageNum(1);
    setFilterValues((s) => ({ ...s, [k]: v }));
  };

  return (
    <div className="space-y-4">
      <div className="bg-spotify-gray border border-spotify-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-3 text-sm text-spotify-muted">
          <Filter className="w-4 h-4" /> Filters
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
          <FilterSelect
            label="Pain category"
            value={filterValues.pain_category}
            options={filters.pain_categories || []}
            onChange={(v) => onFilter("pain_category", v)}
          />
          <FilterSelect
            label="Geography"
            value={filterValues.geography}
            options={filters.geographies || []}
            onChange={(v) => onFilter("geography", v)}
          />
          <FilterSelect
            label="Listening style"
            value={filterValues.listening_style}
            options={filters.listening_styles || []}
            onChange={(v) => onFilter("listening_style", v)}
          />
          <FilterSelect
            label="Source"
            value={filterValues.source}
            options={filters.sources || []}
            onChange={(v) => onFilter("source", v)}
          />
          <label className="flex items-center gap-2 text-spotify-text cursor-pointer pt-5">
            <input
              type="checkbox"
              checked={filterValues.discovery_only}
              onChange={(e) => onFilter("discovery_only", e.target.checked)}
              className="accent-spotify-green w-4 h-4"
            />
            Discovery only
          </label>
        </div>
      </div>

      <div className="bg-spotify-gray border border-spotify-border rounded-xl overflow-hidden">
        <div className="px-4 py-2 border-b border-spotify-border text-xs text-spotify-muted">
          {loading ? "Loading…" : `${page?.total.toLocaleString() ?? 0} matching reviews`}
        </div>
        <div className="divide-y divide-spotify-border max-h-[600px] overflow-y-auto">
          {(page?.items ?? []).map((it: Insight) => (
            <div key={it.review_id} className="p-4 hover:bg-spotify-panel">
              <div className="flex flex-wrap items-center gap-2 text-xs mb-2">
                <Badge color="green">{it.source}</Badge>
                {it.country && <Badge>{it.country.toUpperCase()}</Badge>}
                {it.pain_category && <Badge color="amber">{it.pain_category.replace(/_/g, " ")}</Badge>}
                {it.sentiment_intensity != null && (
                  <span className="text-spotify-muted">intensity {it.sentiment_intensity}/5</span>
                )}
              </div>
              {it.specific_pain && (
                <div className="text-sm text-white font-medium mb-1">{it.specific_pain}</div>
              )}
              {it.verbatim_quote && (
                <div className="text-sm italic text-spotify-text border-l-2 border-spotify-green pl-3">
                  "{it.verbatim_quote}"
                </div>
              )}
            </div>
          ))}
          {!loading && (page?.items?.length ?? 0) === 0 && (
            <div className="p-6 text-center text-spotify-muted text-sm">
              No reviews match these filters.
            </div>
          )}
        </div>
        <div className="px-4 py-3 flex items-center justify-between border-t border-spotify-border text-sm">
          <button
            onClick={() => setPageNum((n) => Math.max(1, n - 1))}
            disabled={pageNum === 1}
            className="px-3 py-1 rounded bg-spotify-panel hover:bg-spotify-border disabled:opacity-30"
          >
            ← Prev
          </button>
          <span className="text-spotify-muted">
            Page {pageNum} / {totalPages}
          </span>
          <button
            onClick={() => setPageNum((n) => Math.min(totalPages, n + 1))}
            disabled={pageNum >= totalPages}
            className="px-3 py-1 rounded bg-spotify-panel hover:bg-spotify-border disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-spotify-muted">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-spotify-black border border-spotify-border rounded px-2 py-1.5 text-sm text-spotify-text focus:outline-none focus:border-spotify-green"
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o.replace(/_/g, " ")}
          </option>
        ))}
      </select>
    </label>
  );
}

function Badge({ children, color = "gray" }: { children: React.ReactNode; color?: "gray" | "green" | "amber" }) {
  const styles = {
    gray: "bg-spotify-border text-spotify-text",
    green: "bg-spotify-green/15 text-spotify-green",
    amber: "bg-amber-500/15 text-amber-400",
  };
  return <span className={`px-2 py-0.5 rounded-md text-xs ${styles[color]}`}>{children}</span>;
}
