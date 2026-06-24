"use client";

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Info } from "lucide-react";
import type { Stats } from "../lib/api";
import { formatPainCategory } from "../lib/format";

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "#1ED760",
  negative: "#E91429",
  neutral: "#71717A",
  mixed: "#FACC15",
};

export function PainCategoriesChart({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .filter(([k]) => k && k !== "none")
    .map(([name, value]) => ({
      name: formatPainCategory(name),
      value,
    }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6);

  const maxVal = rows.length ? Math.max(...rows.map((r) => r.value)) : 250;
  const xMax = Math.ceil(maxVal / 50) * 50 || 250;

  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-5 flex flex-col h-[340px]">
      <div className="flex items-center gap-2 mb-6">
        <h2 className="text-lg font-semibold">Pain Categories</h2>
        <Info className="w-4 h-4 text-app-muted stroke-2" aria-hidden />
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ top: 0, right: 8, left: 4, bottom: 24 }}
          >
            <XAxis
              type="number"
              domain={[0, xMax]}
              tick={{ fill: "#A7A7A7", fontSize: 11 }}
              axisLine={{ stroke: "#282828" }}
              tickLine={false}
              ticks={[0, xMax * 0.2, xMax * 0.4, xMax * 0.6, xMax * 0.8, xMax].map(Math.round)}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={148}
              tick={{ fill: "#FFFFFF", fontSize: 13, fontWeight: 500 }}
              axisLine={{ stroke: "#282828" }}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{ background: "#121212", border: "1px solid #282828", borderRadius: 8 }}
              labelStyle={{ color: "#fff" }}
              cursor={{ fill: "rgba(30,215,96,0.06)" }}
            />
            <Bar dataKey="value" fill="#1ED760" barSize={16} radius={0} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-app-muted text-center -mt-1">Number of Reviews</p>
    </div>
  );
}

export function SentimentDonut({ stats }: { stats: Stats | null }) {
  const total = stats?.total_items ?? 0;
  const dist = stats?.sentiment_distribution ?? {};
  const rows = Object.entries(dist)
    .map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      key: name.toLowerCase(),
      value,
    }))
    .sort((a, b) => b.value - a.value);

  if (rows.length === 0 && total > 0) {
    rows.push({ name: "Neutral", key: "neutral", value: total });
  }

  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-5 flex flex-col h-[340px]">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold">Sentiment Distribution</h2>
        <Info className="w-4 h-4 text-app-muted stroke-2" aria-hidden />
      </div>
      <div className="flex-1 flex items-center justify-center gap-8 min-h-0">
        <div className="relative w-48 h-48 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={rows}
                dataKey="value"
                nameKey="name"
                innerRadius={52}
                outerRadius={76}
                paddingAngle={1}
                stroke="#121212"
                strokeWidth={2}
              >
                {rows.map((row) => (
                  <Cell key={row.key} fill={SENTIMENT_COLORS[row.key] ?? "#71717A"} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-2xl font-bold text-white">{total.toLocaleString()}</span>
            <span className="text-xs text-app-muted">Total Reviews</span>
          </div>
        </div>
        <div className="flex flex-col gap-4 min-w-[148px]">
          {rows.map((row) => {
            const pct = total ? Math.round((row.value / total) * 100) : 0;
            return (
              <div key={row.key} className="flex items-center justify-between text-sm gap-3">
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: SENTIMENT_COLORS[row.key] ?? "#71717A" }}
                  />
                  <span className="text-app-text">
                    {row.name} ({pct}%)
                  </span>
                </div>
                <span className="text-app-text tabular-nums">{row.value.toLocaleString()}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function PainCategoryBar({ data }: { data: Record<string, number> }) {
  return <PainCategoriesChart data={data} />;
}

export function SourcePie({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-5">
      <h3 className="text-sm font-semibold mb-3">Source distribution</h3>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius={55} outerRadius={90}>
            {rows.map((_, i) => (
              <Cell key={i} fill="#1ED760" stroke="#121212" />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: "#121212", border: "1px solid #282828" }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
