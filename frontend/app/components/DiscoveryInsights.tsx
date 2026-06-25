"use client";

import { useEffect, useState } from "react";
import { Compass, RotateCw, AlertTriangle, Target } from "lucide-react";
import { api, type DiscoveryInsightsPayload, type DiscoveryInsightSection } from "../lib/api";

type SectionKey =
  | "discovery_struggles"
  | "repetition_causes"
  | "discovery_frustrations"
  | "discovery_unmet_needs";

const SECTIONS: { key: SectionKey; title: string; icon: typeof Compass; accent: string }[] = [
  {
    key: "discovery_struggles",
    title: "Why users struggle to discover new music",
    icon: Compass,
    accent: "text-app-green",
  },
  {
    key: "repetition_causes",
    title: "What causes repetitive listening",
    icon: RotateCw,
    accent: "text-amber-400",
  },
  {
    key: "discovery_frustrations",
    title: "Discovery frustrations",
    icon: AlertTriangle,
    accent: "text-red-400",
  },
  {
    key: "discovery_unmet_needs",
    title: "Discovery unmet needs",
    icon: Target,
    accent: "text-sky-400",
  },
];

function SectionCard({ title, icon: Icon, accent, section }: {
  title: string;
  icon: typeof Compass;
  accent: string;
  section: DiscoveryInsightSection;
}) {
  const groups = (section.groups ?? []).filter((g) => !g.label.startsWith("Other"));
  const otherGroup = (section.groups ?? []).find((g) => g.label.startsWith("Other"));
  const maxCount = Math.max(1, ...groups.map((g) => g.count));

  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-5 flex flex-col gap-4 h-full">
      <header className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-app-bg border border-app-border shrink-0">
          <Icon className={`w-5 h-5 ${accent} stroke-2 fill-none`} />
        </div>
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-white leading-tight">{title}</h3>
          <p className="text-xs text-app-muted mt-1">
            {section.pool_size.toLocaleString()} relevant reviews ({section.pool_share_of_corpus} of corpus)
          </p>
        </div>
      </header>

      <ul className="flex flex-col gap-3">
        {groups.length === 0 && (
          <li className="text-sm text-app-muted">No grouped findings yet for this segment.</li>
        )}
        {groups.map((group) => {
          const widthPct = Math.max(4, Math.round((group.count / maxCount) * 100));
          return (
            <li key={group.label} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium text-white truncate" title={group.label}>
                  {group.label}
                </span>
                <span className="text-xs text-app-muted whitespace-nowrap">
                  {group.count.toLocaleString()} · {group.share_of_pool || group.share_of_corpus}
                </span>
              </div>
              <div className="h-1.5 bg-app-bg rounded-full overflow-hidden">
                <div className={`h-full bg-app-green/80`} style={{ width: `${widthPct}%` }} />
              </div>
              {group.examples?.[0] && (
                <p className="text-xs text-app-muted italic leading-snug">
                  e.g. {group.examples[0]}
                </p>
              )}
            </li>
          );
        })}
      </ul>

      {otherGroup && otherGroup.count > 0 && (
        <p className="text-[11px] text-app-muted mt-auto pt-2 border-t border-app-border">
          + {otherGroup.count.toLocaleString()} broader discovery signals ({otherGroup.share_of_pool || otherGroup.share_of_corpus}) without a dedicated sub-pattern.
        </p>
      )}
    </div>
  );
}

export function DiscoveryInsights() {
  const [data, setData] = useState<DiscoveryInsightsPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .discoveryInsights()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: Error) => {
        if (!cancelled) setErr(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (err) {
    return (
      <div className="bg-amber-900/30 border border-amber-700 text-amber-200 rounded-lg p-4 text-sm">
        Could not load discovery insights: {err}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {SECTIONS.map(({ key }) => (
          <div key={key} className="bg-app-panel border border-app-border rounded-lg h-72 animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <section className="flex flex-col gap-5">
      <header className="flex items-baseline justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-lg font-semibold text-white">Discovery Insights</h2>
          <p className="text-sm text-app-muted">
            Dedicated grouping of why discovery breaks down — counts derived from{" "}
            <span className="text-white font-medium">{data.totals.total_reviews.toLocaleString()}</span> reviews.
            Discovery-related: <span className="text-white">{data.totals.discovery_related.toLocaleString()}</span>{" "}
            ({data.totals.discovery_related_share}) · Repetition-related:{" "}
            <span className="text-white">{data.totals.repetition_related.toLocaleString()}</span>{" "}
            ({data.totals.repetition_related_share}).
          </p>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {SECTIONS.map(({ key, title, icon, accent }) => (
          <SectionCard
            key={key}
            title={title}
            icon={icon}
            accent={accent}
            section={data[key]}
          />
        ))}
      </div>
    </section>
  );
}
