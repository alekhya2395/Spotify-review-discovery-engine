"use client";

import { useEffect, useState } from "react";
import { api, type Stats, type Theme } from "./lib/api";
import { AppHeader, type NavTab } from "./components/AppHeader";
import { MobileNavBar } from "./components/MobileNavBar";
import { KpiCards } from "./components/KpiCards";
import { PainCategoriesChart, SentimentDonut } from "./components/Charts";
import { InsightsTable } from "./components/InsightsTable";
import { ThemeCards } from "./components/ThemeCards";
import { ChatPanel } from "./components/ChatPanel";
import { WorkflowDiagram } from "./components/WorkflowDiagram";

function isDiscoveryQuestion(query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  if (q.includes("?")) return true;
  return /^(why|what|how|when|where|who|which|tell me|explain|summarize|compare|list|show|describe)\b/.test(q);
}

export default function Page() {
  const [tab, setTab] = useState<NavTab>("dashboard");
  const [stats, setStats] = useState<Stats | null>(null);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [healthErr, setHealthErr] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [chatQuestion, setChatQuestion] = useState("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const load = () => {
      api
        .health()
        .then(() => {
          if (cancelled) return;
          setHealthErr(null);
          return Promise.all([api.stats(), api.themes()]);
        })
        .then((result) => {
          if (cancelled || !result) return;
          const [s, t] = result;
          setStats(s);
          setThemes(t.themes || []);
        })
        .catch((e) => {
          if (cancelled) return;
          setHealthErr(e.message);
          timer = setTimeout(load, 5000);
        });
    };

    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  const handleSearchChange = (q: string) => {
    if (isDiscoveryQuestion(q)) {
      setChatQuestion(q.trim());
      setTab("chat");
      return;
    }
    setSearchQuery(q);
    if (tab !== "dashboard") setTab("dashboard");
  };

  return (
    <div className="min-h-screen flex flex-col bg-app-bg text-app-text font-sans">
      <AppHeader
        activeTab={tab}
        onTabChange={setTab}
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
      />

      {healthErr && (
        <div className="mx-4 md:mx-6 mt-4 bg-amber-900/30 border border-amber-700 text-amber-200 rounded-lg p-3 text-sm">
          <strong>Backend unreachable.</strong> {healthErr}
          <br />
          On Vercel, set <code>BACKEND_URL</code> to your Railway URL (e.g.{" "}
          <code>https://spotify-api-production-73c6.up.railway.app</code>) and redeploy.
        </div>
      )}

      <MobileNavBar
        activeTab={tab}
        onTabChange={setTab}
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
      />

      <main className="flex-1 p-4 md:p-6 flex flex-col gap-6 max-w-[1600px] mx-auto w-full">
        {tab === "dashboard" && (
          <>
            <KpiCards stats={stats} />
            <section className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-6 xl:h-[340px]">
              <PainCategoriesChart data={stats?.pain_categories ?? {}} />
              <SentimentDonut stats={stats} />
            </section>
            <InsightsTable searchQuery={searchQuery} />
          </>
        )}

        {tab === "insights" && <ThemeCards themes={themes} />}
        {tab === "workflow" && <WorkflowDiagram />}
        {tab === "chat" && (
          <ChatPanel
            reviewCount={stats?.total_items}
            pendingQuestion={chatQuestion}
            onPendingQuestionConsumed={() => setChatQuestion("")}
          />
        )}
      </main>
    </div>
  );
}
