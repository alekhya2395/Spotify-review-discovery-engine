"use client";

import { useEffect, useState } from "react";
import { Headphones } from "lucide-react";
import { api, type Stats, type Theme } from "./lib/api";
import { MetricsBar } from "./components/MetricsBar";
import { PainCategoryBar, SourcePie } from "./components/Charts";
import { ThemeCards } from "./components/ThemeCards";
import { ReviewExplorer } from "./components/ReviewExplorer";
import { ChatPanel } from "./components/ChatPanel";
import { WorkflowDiagram } from "./components/WorkflowDiagram";
import { ReportView } from "./components/ReportView";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "themes", label: "Themes" },
  { id: "explorer", label: "Review Explorer" },
  { id: "chat", label: "Chat with Insights" },
  { id: "report", label: "Full Report" },
  { id: "workflow", label: "Workflow (1-slider)" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Page() {
  const [tab, setTab] = useState<TabId>("overview");
  const [stats, setStats] = useState<Stats | null>(null);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [healthErr, setHealthErr] = useState<string | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch((e) => setHealthErr(e.message));
    api.themes().then((t) => setThemes(t.themes || [])).catch(() => setThemes([]));
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-4 md:px-8 py-8 space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-spotify-green flex items-center justify-center">
            <Headphones className="w-5 h-5 text-black" />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-white">
              Spotify Discovery Insights Engine
            </h1>
            <p className="text-sm text-spotify-muted">
              AI-powered review analysis · App Store · Play Store · Reddit · Grounded chat
            </p>
          </div>
        </div>
        {healthErr && (
          <div className="bg-amber-900/30 border border-amber-700 text-amber-200 rounded-lg p-3 text-sm">
            ⚠ Backend unreachable: {healthErr}. Set <code>NEXT_PUBLIC_API_URL</code> in your env.
          </div>
        )}
      </header>

      <MetricsBar stats={stats} />

      <nav className="flex flex-wrap gap-2 border-b border-spotify-border pb-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition ${
              tab === t.id
                ? "bg-spotify-gray text-white border-b-2 border-spotify-green"
                : "text-spotify-muted hover:text-white"
            }`}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "overview" && stats && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SourcePie data={stats.sources} />
            <PainCategoryBar data={stats.pain_categories} />
          </div>
        )}

        {tab === "themes" && <ThemeCards themes={themes} />}
        {tab === "explorer" && <ReviewExplorer />}
        {tab === "chat" && <ChatPanel />}
        {tab === "report" && <ReportView />}
        {tab === "workflow" && <WorkflowDiagram />}
      </main>

      <footer className="pt-8 border-t border-spotify-border text-xs text-spotify-muted">
        Built for the Next Leap PM Fellowship · Graduation Project Part 1 · AI-Powered Review Discovery Engine
      </footer>
    </div>
  );
}
