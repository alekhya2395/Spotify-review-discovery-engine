"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, Quote } from "lucide-react";
import type { Theme } from "../lib/api";

function SeverityBar({ value }: { value: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className={`h-1.5 w-4 rounded-sm ${
            i <= value ? "bg-spotify-green" : "bg-spotify-border"
          }`}
        />
      ))}
    </div>
  );
}

export function ThemeCards({ themes }: { themes: Theme[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (!themes.length) {
    return (
      <div className="bg-spotify-gray border border-spotify-border rounded-xl p-8 text-center text-spotify-muted">
        Themes will appear here after running the synthesizer.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {themes.map((t) => {
        const isOpen = !!open[t.theme_id];
        return (
          <div
            key={t.theme_id}
            className="bg-spotify-gray border border-spotify-border rounded-xl overflow-hidden"
          >
            <button
              onClick={() => setOpen((s) => ({ ...s, [t.theme_id]: !isOpen }))}
              className="w-full flex items-start gap-4 p-5 text-left hover:bg-spotify-panel transition"
            >
              <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-spotify-green/15 text-spotify-green flex items-center justify-center font-bold">
                {t.theme_id}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-3 mb-1">
                  <h3 className="text-base font-semibold text-white truncate">{t.theme_name}</h3>
                  {isOpen ? (
                    <ChevronUp className="w-4 h-4 text-spotify-muted flex-shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-spotify-muted flex-shrink-0" />
                  )}
                </div>
                <p className="text-sm text-spotify-muted line-clamp-2">{t.one_line_summary}</p>
                <div className="flex items-center gap-4 mt-3 text-xs text-spotify-muted">
                  <span>~{t.estimated_frequency_pct}% of reviews</span>
                  <div className="flex items-center gap-2">
                    <span>Severity</span>
                    <SeverityBar value={t.severity} />
                  </div>
                  <span className="hidden md:inline">· {t.dominant_segment}</span>
                </div>
              </div>
            </button>

            {isOpen && (
              <div className="px-5 pb-5 pt-1 border-t border-spotify-border space-y-4">
                <div className="grid md:grid-cols-2 gap-4 mt-4">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-spotify-muted mb-1">Root cause</div>
                    <p className="text-sm text-spotify-text">{t.root_cause_hypothesis}</p>
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-wider text-spotify-muted mb-1">What users want</div>
                    <p className="text-sm text-spotify-text">{t.what_users_want_instead}</p>
                  </div>
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider text-spotify-muted mb-2">Representative quotes</div>
                  <div className="space-y-2">
                    {t.representative_quotes.map((q, i) => (
                      <div
                        key={i}
                        className="flex gap-2 p-3 bg-spotify-black border border-spotify-border rounded-lg"
                      >
                        <Quote className="w-4 h-4 text-spotify-green flex-shrink-0 mt-0.5" />
                        <p className="text-sm italic text-spotify-text">{q}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
