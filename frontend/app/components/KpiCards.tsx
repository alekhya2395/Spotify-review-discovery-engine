"use client";

import { Frown, MessageSquare, Search, TriangleAlert } from "lucide-react";
import type { Stats } from "../lib/api";
import { formatPainCategory } from "../lib/format";

function KpiIcon({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-2.5 rounded-lg bg-app-bg border border-app-border shrink-0">
      {children}
    </div>
  );
}

export function KpiCards({ stats }: { stats: Stats | null }) {
  const iconClass = "w-6 h-6 text-app-green stroke-[2] fill-none";

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6">
      <div className="bg-app-panel border border-app-border rounded-lg p-5 flex items-start gap-4">
        <KpiIcon>
          <MessageSquare className={iconClass} />
        </KpiIcon>
        <div>
          <h3 className="text-sm text-app-muted font-medium mb-1">Total Reviews Analyzed</h3>
          <p className="text-3xl font-bold tracking-tight text-white">
            {stats ? stats.total_items.toLocaleString() : "—"}
          </p>
        </div>
      </div>

      <div className="bg-app-panel border border-app-border rounded-lg p-5 flex items-start gap-4">
        <KpiIcon>
          <Search className={iconClass} />
        </KpiIcon>
        <div>
          <h3 className="text-sm text-app-muted font-medium mb-1">Discovery Related</h3>
          <p className="text-3xl font-bold tracking-tight text-white">
            {stats ? stats.discovery_related.toLocaleString() : "—"}
          </p>
        </div>
      </div>

      <div className="bg-app-panel border border-app-border rounded-lg p-5 flex items-start gap-4">
        <KpiIcon>
          <TriangleAlert className={iconClass} />
        </KpiIcon>
        <div>
          <h3 className="text-sm text-app-muted font-medium mb-1">Top Pain Category</h3>
          <p className="text-2xl font-bold tracking-tight text-white mt-1 leading-none">
            {stats?.top_pain_category ? formatPainCategory(stats.top_pain_category) : "—"}
          </p>
        </div>
      </div>

      <div className="bg-app-panel border border-app-border rounded-lg p-5 flex items-start gap-4">
        <KpiIcon>
          <Frown className={iconClass} />
        </KpiIcon>
        <div>
          <h3 className="text-sm text-app-muted font-medium mb-1">Avg Sentiment</h3>
          <p className="text-3xl font-bold tracking-tight text-white">
            {stats != null ? stats.avg_sentiment.toFixed(2) : "—"}
          </p>
        </div>
      </div>
    </section>
  );
}
