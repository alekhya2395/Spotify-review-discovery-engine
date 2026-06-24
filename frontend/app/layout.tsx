import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spotify Review Discovery Engine",
  description:
    "AI-powered review analysis dashboard for Spotify — pain categories, sentiment, and searchable user insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-app-bg text-app-text min-h-screen antialiased">{children}</body>
    </html>
  );
}
