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

const palette = ["#1DB954", "#1ED760", "#169c46", "#0e7a36", "#0a5a28", "#7DDB9E", "#a2e8b8"];

export function SourcePie({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data).map(([name, value]) => ({ name, value }));
  return (
    <div className="bg-spotify-gray border border-spotify-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-3">Source distribution</h3>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={rows}
            dataKey="value"
            nameKey="name"
            innerRadius={55}
            outerRadius={90}
            paddingAngle={2}
            label={(entry: { name: string; value: number }) => `${entry.name}: ${entry.value}`}
          >
            {rows.map((_, i) => (
              <Cell key={i} fill={palette[i % palette.length]} stroke="#0a0a0a" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#181818", border: "1px solid #2a2a2a", borderRadius: 8 }}
            labelStyle={{ color: "#e8e8e8" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export function PainCategoryBar({ data }: { data: Record<string, number> }) {
  const rows = Object.entries(data)
    .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }))
    .sort((a, b) => b.value - a.value);
  return (
    <div className="bg-spotify-gray border border-spotify-border rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-3">Pain category breakdown</h3>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={rows} margin={{ top: 8, right: 10, left: 0, bottom: 60 }}>
          <XAxis
            dataKey="name"
            angle={-30}
            textAnchor="end"
            tick={{ fill: "#8a8a8a", fontSize: 11 }}
            interval={0}
          />
          <YAxis tick={{ fill: "#8a8a8a", fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#181818", border: "1px solid #2a2a2a", borderRadius: 8 }}
            labelStyle={{ color: "#e8e8e8" }}
            cursor={{ fill: "#222" }}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}>
            {rows.map((_, i) => (
              <Cell key={i} fill={palette[i % palette.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
