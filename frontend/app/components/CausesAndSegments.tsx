"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Compass,
  Headphones,
  Users,
  Crown,
  Volume2,
  Music,
  Target,
} from "lucide-react";
import {
  api,
  type RootCause,
  type RootCausesPayload,
  type UserSegment,
  type UserSegmentsPayload,
} from "../lib/api";

const SEGMENT_ICONS: Record<string, typeof Compass> = {
  "Discovery Seeker": Compass,
  "Playlist User": Music,
  "Heavy Listener": Headphones,
  "Casual Listener": Users,
  "Premium User": Crown,
  "Free User": Volume2,
};

const SEGMENT_ACCENTS: Record<string, string> = {
  "Discovery Seeker": "text-app-green",
  "Playlist User": "text-sky-400",
  "Heavy Listener": "text-fuchsia-400",
  "Casual Listener": "text-slate-300",
  "Premium User": "text-amber-300",
  "Free User": "text-red-400",
};

function RootCauseRow({ cause, maxCount }: { cause: RootCause; maxCount: number }) {
  const widthPct = Math.max(4, Math.round((cause.count / maxCount) * 100));
  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h4 className="text-sm font-semibold text-white" title={cause.label}>
          {cause.label}
        </h4>
        <span className="text-xs text-app-muted whitespace-nowrap">
          {cause.count.toLocaleString()} reviews · {cause.share_of_corpus}
        </span>
      </div>
      <p className="text-xs text-app-muted leading-snug">{cause.summary}</p>
      <div className="h-1.5 bg-app-bg rounded-full overflow-hidden">
        <div className="h-full bg-app-green/80" style={{ width: `${widthPct}%` }} />
      </div>
      {cause.top_pain_categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {cause.top_pain_categories.map((p) => (
            <span
              key={p.key}
              className="text-[10px] uppercase tracking-wider text-app-muted bg-app-bg border border-app-border rounded-full px-2 py-0.5"
            >
              {p.key.replace(/_/g, " ")} · {p.count}
            </span>
          ))}
        </div>
      )}
      {cause.examples[0] && (
        <p className="text-xs text-app-muted italic leading-snug">e.g. {cause.examples[0]}</p>
      )}
    </div>
  );
}

function SegmentCard({ segment }: { segment: UserSegment }) {
  const Icon = SEGMENT_ICONS[segment.name] || Target;
  const accent = SEGMENT_ACCENTS[segment.name] || "text-app-green";
  const hasData = segment.count > 0;

  return (
    <div className="bg-app-panel border border-app-border rounded-lg p-5 flex flex-col gap-4 h-full">
      <header className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-app-bg border border-app-border shrink-0">
          <Icon className={`w-5 h-5 ${accent} stroke-2 fill-none`} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="text-base font-semibold text-white leading-tight">{segment.name}</h3>
            <span className="text-xs text-app-muted whitespace-nowrap">
              {segment.count.toLocaleString()} · {segment.share_of_corpus}
            </span>
          </div>
          <p className="text-xs text-app-muted mt-1 leading-snug">{segment.description}</p>
        </div>
      </header>

      {!hasData && (
        <p className="text-sm text-app-muted">No reviews matched this segment yet.</p>
      )}

      {hasData && (
        <dl className="flex flex-col gap-3 text-sm">
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3" /> Primary frustration
            </dt>
            <dd className="text-white mt-0.5">
              {segment.primary_frustration ? (
                <>
                  {segment.primary_frustration.label}{" "}
                  <span className="text-app-muted text-xs">
                    ({segment.primary_frustration.count} · {segment.primary_frustration.share_of_segment})
                  </span>
                </>
              ) : (
                <span className="text-app-muted text-xs">—</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <Compass className="w-3 h-3" /> Discovery challenge
            </dt>
            <dd className="text-white mt-0.5">
              {segment.discovery_challenge ? (
                <>
                  {segment.discovery_challenge.label}{" "}
                  <span className="text-app-muted text-xs">
                    ({segment.discovery_challenge.count} · {segment.discovery_challenge.share_of_segment})
                  </span>
                </>
              ) : (
                <span className="text-app-muted text-xs">—</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-app-muted flex items-center gap-1.5">
              <Target className="w-3 h-3" /> Unmet need
            </dt>
            <dd className="text-white mt-0.5">
              {segment.unmet_need ? (
                <>
                  {segment.unmet_need.label}{" "}
                  <span className="text-app-muted text-xs">
                    ({segment.unmet_need.count} · {segment.unmet_need.share_of_segment})
                  </span>
                </>
              ) : (
                <span className="text-app-muted text-xs">—</span>
              )}
            </dd>
          </div>
        </dl>
      )}

      {hasData && Object.keys(segment.sentiment_mix).length > 0 && (
        <div className="pt-3 mt-auto border-t border-app-border flex flex-wrap gap-1.5">
          {Object.entries(segment.sentiment_mix).map(([name, pct]) => (
            <span
              key={name}
              className="text-[10px] uppercase tracking-wider text-app-muted bg-app-bg border border-app-border rounded-full px-2 py-0.5"
            >
              {name} {pct}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function CausesAndSegments() {
  const [causes, setCauses] = useState<RootCausesPayload | null>(null);
  const [segments, setSegments] = useState<UserSegmentsPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.rootCauses(), api.userSegments()])
      .then(([rc, us]) => {
        if (cancelled) return;
        setCauses(rc);
        setSegments(us);
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
        Could not load root causes and segments: {err}
      </div>
    );
  }

  const maxCauseCount = Math.max(1, ...(causes?.causes ?? []).map((c) => c.count));

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-4">
        <header>
          <h2 className="text-lg font-semibold text-white">Root Cause Analysis</h2>
          <p className="text-sm text-app-muted">
            What's structurally behind the most common pain points — grouped, counted, and ranked across{" "}
            <span className="text-white font-medium">
              {causes ? causes.total_reviews.toLocaleString() : "—"}
            </span>{" "}
            reviews.
          </p>
        </header>

        {!causes && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-app-panel border border-app-border rounded-lg h-32 animate-pulse" />
            ))}
          </div>
        )}

        {causes && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {causes.causes.map((cause) => (
              <RootCauseRow key={cause.label} cause={cause} maxCount={maxCauseCount} />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <header>
          <h2 className="text-lg font-semibold text-white">User Segments</h2>
          <p className="text-sm text-app-muted">
            Each segment's primary frustration, discovery challenge, and unmet need — computed from the
            review text and the inferred listening profile.
          </p>
        </header>

        {!segments && (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="bg-app-panel border border-app-border rounded-lg h-64 animate-pulse" />
            ))}
          </div>
        )}

        {segments && (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {segments.segments.map((seg) => (
              <SegmentCard key={seg.name} segment={seg} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
