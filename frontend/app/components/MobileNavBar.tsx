"use client";

import { Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type { NavTab } from "./AppHeader";

type Props = {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
};

const NAV: { id: NavTab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "insights", label: "Insights" },
  { id: "discovery", label: "Discovery" },
  { id: "workflow", label: "Workflow" },
  { id: "chat", label: "Chat" },
];

export function MobileNavBar({ activeTab, onTabChange, searchQuery, onSearchChange }: Props) {
  const [draft, setDraft] = useState(searchQuery);

  useEffect(() => {
    setDraft(searchQuery);
  }, [searchQuery]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSearchChange(draft.trim());
    if (activeTab !== "dashboard") onTabChange("dashboard");
  };

  return (
    <div className="lg:hidden border-b border-app-border bg-app-bg px-4 py-3 space-y-3">
      <div className="flex gap-1 overflow-x-auto">
        {NAV.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => onTabChange(id)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap ${
              activeTab === id
                ? "bg-app-green text-black"
                : "bg-app-panel border border-app-border text-app-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <form onSubmit={submit} className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-app-muted pointer-events-none" />
        <input
          type="search"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Search reviews…"
          className="w-full bg-app-panel border border-app-border rounded pl-8 pr-3 py-2 text-sm text-app-text placeholder:text-app-muted focus:outline-none focus:border-gray-500"
        />
      </form>
    </div>
  );
}
