"use client";

import { Moon, Search } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

export type NavTab = "dashboard" | "insights" | "discovery" | "causes" | "workflow" | "chat";

const NAV: { id: NavTab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "insights", label: "Insights" },
  { id: "discovery", label: "Discovery" },
  { id: "causes", label: "Causes" },
  { id: "workflow", label: "Workflow" },
  { id: "chat", label: "Chat" },
];

type Props = {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
};

export function AppHeader({ activeTab, onTabChange, searchQuery, onSearchChange }: Props) {
  const [draft, setDraft] = useState(searchQuery);

  useEffect(() => {
    setDraft(searchQuery);
  }, [searchQuery]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSearchChange(draft.trim());
  };

  return (
    <header className="border-b border-app-border bg-app-bg px-6 h-16 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3 shrink-0">
        <svg className="w-8 h-8 fill-app-green shrink-0" viewBox="0 0 24 24" aria-hidden>
          <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.24 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.84.24 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.6.18-1.2.72-1.38 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.239.54-.959.72-1.56.3z" />
        </svg>
        <div className="font-bold text-lg leading-tight tracking-tight">
          <div className="text-white">Spotify Review</div>
          <div className="text-app-green">Discovery Engine</div>
        </div>
      </div>

      <nav className="hidden md:flex items-center gap-8 h-full">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onTabChange(item.id)}
            className={`relative h-full flex items-center text-sm font-medium whitespace-nowrap transition-colors ${
              activeTab === item.id ? "text-app-green" : "text-app-text hover:text-app-muted"
            }`}
          >
            {item.label}
            {activeTab === item.id && (
              <span className="absolute bottom-0 left-0 w-full h-[2px] bg-app-green" />
            )}
          </button>
        ))}

        <form onSubmit={submit} className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-app-muted pointer-events-none" />
          <input
            type="search"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Search or ask about reviews…"
            className="w-44 xl:w-52 bg-app-bg border border-app-border rounded pl-8 pr-3 py-1.5 text-sm text-app-text placeholder:text-app-muted focus:outline-none focus:border-gray-500 hover:border-gray-500 transition-colors"
          />
        </form>
      </nav>

      <div className="flex items-center gap-4 shrink-0">
        <button
          type="button"
          className="p-2 rounded-full hover:bg-app-border transition-colors"
          aria-label="Dark mode"
        >
          <Moon className="w-5 h-5 text-app-text stroke-2" />
        </button>
      </div>
    </header>
  );
}
