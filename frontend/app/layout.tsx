import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spotify Discovery Insights Engine",
  description:
    "An AI-powered review analysis system that ingests App Store, Play Store and Reddit feedback to surface why users struggle with music discovery on Spotify.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-spotify-black text-spotify-text min-h-screen">{children}</body>
    </html>
  );
}
