"use client";

import { useEffect, useState } from "react";
import { FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../lib/api";

export function ReportView() {
  const [md, setMd] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .report()
      .then((r) => setMd(r.markdown || ""))
      .catch(() => setMd(""))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="bg-spotify-gray border border-spotify-border rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-4 h-4 text-spotify-green" />
        <h3 className="text-sm font-semibold text-white">Discovery Insights Report</h3>
      </div>
      {loading ? (
        <p className="text-spotify-muted text-sm">Loading…</p>
      ) : md ? (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
        </div>
      ) : (
        <p className="text-spotify-muted text-sm">Report not generated yet. Run the synthesizer.</p>
      )}
    </div>
  );
}
