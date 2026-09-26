"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useLender, useLogAppetite } from "@/lib/queries/lenders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

const SIGNAL_COLORS: Record<string, string> = {
  hungry: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  active: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  selective: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  paused: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

export default function LenderDetailPage({ params }: { params: Promise<{ lenderId: string }> }) {
  const { lenderId } = use(params);
  const { data: lender } = useLender(lenderId);
  const logAppetite = useLogAppetite(lenderId);

  const [showAppetiteForm, setShowAppetiteForm] = useState(false);
  const [signal, setSignal] = useState("active");
  const [detail, setDetail] = useState("");

  const handleLogAppetite = async (e: React.FormEvent) => {
    e.preventDefault();
    await logAppetite.mutateAsync({
      appetite_signal: signal,
      source_detail: detail || undefined,
    });
    setShowAppetiteForm(false);
    setDetail("");
  };

  if (!lender) return <p className="p-8 text-muted-foreground">Loading...</p>;

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/lenders" className="text-sm text-muted-foreground hover:text-foreground">&larr; Lenders</Link>
          <h1 className="text-lg font-semibold">{lender.name}</h1>
          <Badge variant="outline">{lender.lender_type.replace(/_/g, " ")}</Badge>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        {/* Current Appetite */}
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Current Appetite</h2>
          <Button size="sm" onClick={() => setShowAppetiteForm(!showAppetiteForm)}>
            {showAppetiteForm ? "Cancel" : "Log Appetite"}
          </Button>
        </div>

        {showAppetiteForm && (
          <Card className="p-4">
            <form onSubmit={handleLogAppetite} className="flex gap-3 items-end">
              <div className="flex gap-2">
                {["hungry", "active", "selective", "paused"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSignal(s)}
                    className={`px-3 py-1.5 rounded text-sm font-medium ${
                      signal === s ? SIGNAL_COLORS[s] : "bg-muted text-muted-foreground"
                    }`}
                  >{s}</button>
                ))}
              </div>
              <Input
                value={detail}
                onChange={(e) => setDetail(e.target.value)}
                placeholder="One-line note (optional)"
                className="flex-1"
              />
              <Button type="submit" disabled={logAppetite.isPending}>
                {logAppetite.isPending ? "Saving..." : "Save"}
              </Button>
            </form>
          </Card>
        )}

        {lender.current_appetite ? (
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded text-sm font-medium ${SIGNAL_COLORS[lender.current_appetite.appetite_signal] || "bg-muted"}`}>
                {lender.current_appetite.appetite_signal}
              </span>
              {lender.current_appetite.is_stale && <Badge variant="destructive">Stale</Badge>}
              {lender.current_appetite.rate_indication && (
                <span className="text-sm text-muted-foreground">Rate: {lender.current_appetite.rate_indication}</span>
              )}
              {lender.current_appetite.ltc_max && (
                <span className="text-sm text-muted-foreground">LTC: {(lender.current_appetite.ltc_max * 100).toFixed(0)}%</span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-2">Recorded {lender.current_appetite.recorded_at}</p>
          </Card>
        ) : (
          <p className="text-sm text-muted-foreground">No appetite data yet</p>
        )}

        {/* Profile */}
        {(lender.credit_committee_notes || lender.notes) && (
          <>
            <h2 className="font-semibold">Profile</h2>
            <Card className="p-4 text-sm space-y-2">
              {lender.credit_committee_notes && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Credit Committee Notes</p>
                  <p className="whitespace-pre-wrap">{lender.credit_committee_notes}</p>
                </div>
              )}
              {lender.notes && (
                <div>
                  <p className="text-muted-foreground text-xs mb-1">Notes</p>
                  <p className="whitespace-pre-wrap">{lender.notes}</p>
                </div>
              )}
            </Card>
          </>
        )}

        {/* Appetite Timeline */}
        {lender.appetite_history && lender.appetite_history.length > 0 && (
          <>
            <h2 className="font-semibold">Appetite History</h2>
            <div className="space-y-1">
              {lender.appetite_history.map((a, i) => (
                <div key={i} className="flex items-center gap-3 text-sm py-1">
                  <span className={`px-2 py-0.5 rounded text-xs ${SIGNAL_COLORS[a.appetite_signal] || "bg-muted"}`}>
                    {a.appetite_signal}
                  </span>
                  {a.source_detail && <span className="text-muted-foreground flex-1 truncate">{a.source_detail}</span>}
                  <span className="text-xs text-muted-foreground">{a.recorded_at}</span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Transactions */}
        {lender.transactions && lender.transactions.length > 0 && (
          <>
            <h2 className="font-semibold">Transaction History</h2>
            <div className="space-y-1">
              {lender.transactions.map((t) => (
                <Card key={t.id} className="p-2 text-sm">
                  <div className="flex items-center gap-3">
                    {t.outcome && <Badge variant={t.outcome === "won" ? "default" : "secondary"}>{t.outcome}</Badge>}
                    {t.property_type && <span>{t.property_type}</span>}
                    {t.geography && <span className="text-muted-foreground">{t.geography}</span>}
                    {t.deal_size && <span className="font-mono">${(t.deal_size / 1e6).toFixed(0)}M</span>}
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
