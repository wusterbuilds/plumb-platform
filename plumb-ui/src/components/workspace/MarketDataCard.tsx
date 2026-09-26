"use client";

import { CheckCircle2, AlertTriangle, XCircle, Loader2, ExternalLink } from "lucide-react";

interface MarketDataCardProps {
  title: string;
  source: string;
  status: string;
  sourceUrl?: string | null;
  confidence?: number | null;
  children?: React.ReactNode;
}

const statusConfig: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  success: {
    icon: <CheckCircle2 className="h-4 w-4" />,
    color: "text-green-600 bg-green-50 border-green-200",
    label: "Complete",
  },
  pending: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: "text-zinc-500 bg-zinc-50 border-zinc-200",
    label: "Pending",
  },
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: "text-blue-600 bg-blue-50 border-blue-200",
    label: "Running",
  },
  empty: {
    icon: <AlertTriangle className="h-4 w-4" />,
    color: "text-amber-600 bg-amber-50 border-amber-200",
    label: "No Data",
  },
  error: {
    icon: <XCircle className="h-4 w-4" />,
    color: "text-red-600 bg-red-50 border-red-200",
    label: "Failed",
  },
};

export function MarketDataCard({
  title,
  source,
  status,
  sourceUrl,
  confidence,
  children,
}: MarketDataCardProps) {
  const cfg = statusConfig[status] ?? statusConfig.pending;

  return (
    <div className={`rounded-lg border p-4 ${cfg.color}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {cfg.icon}
          <h3 className="text-sm font-medium">{title}</h3>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="opacity-70">{cfg.label}</span>
          {confidence != null && (
            <span className="font-mono opacity-60">{(confidence * 100).toFixed(0)}%</span>
          )}
          {sourceUrl && (
            <a
              href={sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="opacity-60 hover:opacity-100"
            >
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
      <p className="text-xs opacity-60 mb-2">{source}</p>
      {children && <div className="text-sm">{children}</div>}
    </div>
  );
}
