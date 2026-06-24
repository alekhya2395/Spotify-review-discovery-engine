const PAIN_LABELS: Record<string, string> = {
  recommendation_quality: "Algorithm Repetition",
  algorithm_repetition: "Algorithm Repetition",
  ui_ux: "UI/UX Issues",
  ui_ux_issues: "UI/UX Issues",
  pricing: "Pricing Complaints",
  pricing_complaints: "Pricing Complaints",
  content_availability: "Content Availability",
  catalog_gaps: "Content Availability",
  listening_behavior: "Listening Behavior",
  social_features: "Social Features",
  discovery: "Discovery",
};

export function formatPainCategory(value?: string | null): string {
  if (!value || value === "none") return "Other";
  const key = value.toLowerCase();
  if (PAIN_LABELS[key]) return PAIN_LABELS[key];
  return value
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
export function formatSource(source?: string | null): string {
  if (!source) return "Unknown";
  const map: Record<string, string> = {
    app_store: "App Store",
    play_store: "Google Play",
    reddit: "Reddit",
    social_media: "Social Media",
    community_forum: "Community Forum",
    web_review: "Web Review",
  };
  return map[source] ?? source.replace(/_/g, " ");
}

const SEGMENT_LABELS: Record<string, string> = {
  free_users: "Free Users",
  premium_users: "Premium Users",
  all_users: "All Users",
  music_explorers: "Music Explorers",
  podcast_listeners: "Podcast Listeners",
  unknown: "All Users",
};

export function formatSegment(style?: string | null): string {
  if (!style) return "All Users";
  const key = style.toLowerCase();
  if (SEGMENT_LABELS[key]) return SEGMENT_LABELS[key];
  return style
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
export function sentimentFromIntensity(intensity?: number | null): string {
  if (intensity == null) return "neutral";
  if (intensity >= 4) return "positive";
  if (intensity <= 2) return "negative";
  return "neutral";
}
