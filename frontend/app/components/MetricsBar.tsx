"use client";

import { BarChart3, Headphones, Repeat, Sparkles } from "lucide-react";
import type { Stats } from "../lib/api";

const cards = [
  { key: "total_items", label: "Reviews analyzed", icon: BarChart3, fmt: (n: number) => n.toLocaleString() },
  { key: "discovery_related", label: "Discovery-related", icon: Headphones, fmt: (n: number) => n.toLocaleString() },
  { key: "repetition_related", label: "Repetition-related", icon: Repeat, fmt: (n: number) => n.toLocaleString() },
  { key: "avg_sentiment", label: "Avg. frustration", icon: Sparkles, fmt: (n: number) => `${n.toFixed(1)} / 5` },
] as const;

export function MetricsBar({ stats }: { stats: Stats | null }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {cards.map(({ key, label, icon: Icon, fmt }) => (
        <div
          key={key}
          className="bg-spotify-gray border border-spotify-border rounded-xl p-5"
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs uppercase tracking-wider text-spotify-muted">{label}</span>
            <Icon className="w-4 h-4 text-spotify-green" />
          </div>
          <div className="text-3xl font-bold text-white">
            {stats ? fmt(stats[key] as number) : "—"}
          </div>
        </div>
      ))}
    </div>
  );
}
