"use client";

import { useLenderMatch } from "@/lib/queries/lenders";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import Link from "next/link";

const SIGNAL_COLORS: Record<string, string> = {
  hungry: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  active: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  selective: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  paused: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export function LenderMatchResults({ dealId }: { dealId: string }) {
  const { data: matches, isLoading } = useLenderMatch(dealId);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading matches...</p>;
  if (!matches?.length) return <p className="text-sm text-muted-foreground">No matching lenders found</p>;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Lender Matches ({matches.length})</h3>
      {matches.map((m) => (
        <Link key={m.lender_id} href={`/lenders/${m.lender_id}`}>
          <Card className="p-3 hover:bg-muted/50 cursor-pointer">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-medium text-sm">{m.lender_name}</span>
                <span className="text-xs text-muted-foreground ml-2">{m.lender_type}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${SIGNAL_COLORS[m.appetite_signal] || "bg-muted"}`}>
                  {m.appetite_signal}
                </span>
                <Badge variant="outline" className="font-mono text-xs">
                  {m.fit_score.toFixed(0)}
                </Badge>
              </div>
            </div>
            <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
              {m.rate_indication && <span>Rate: {m.rate_indication}</span>}
              {m.ltc_max && <span>LTC: {(m.ltc_max * 100).toFixed(0)}%</span>}
            </div>
          </Card>
        </Link>
      ))}
    </div>
  );
}
