"use client";

import { useDistributions } from "@/lib/queries/lenders";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function DistributionTracker({ dealId }: { dealId: string }) {
  const { data: distributions, isLoading } = useDistributions(dealId);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading...</p>;
  if (!distributions?.length) return <p className="text-sm text-muted-foreground">No distributions yet</p>;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium">Distribution Tracker</h3>
      {(distributions as { distribution_id: string; lender_id: string; distributed_at: string; response: { response_type: string; notes?: string } | null }[]).map((d) => (
        <Card key={d.distribution_id} className="p-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs">{d.lender_id.slice(0, 8)}</span>
            {d.response ? (
              <Badge variant={
                d.response.response_type === "term_sheet" ? "default" :
                d.response.response_type === "pass" ? "destructive" : "secondary"
              }>
                {d.response.response_type}
              </Badge>
            ) : (
              <Badge variant="outline">Pending</Badge>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
