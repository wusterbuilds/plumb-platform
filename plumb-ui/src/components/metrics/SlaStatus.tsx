"use client";

import { useAlerts, useAcknowledgeAlert } from "@/lib/queries/metrics";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function SlaStatus() {
  const { data: alerts, isLoading } = useAlerts();
  const ack = useAcknowledgeAlert();

  return (
    <Card className="p-4">
      <h3 className="text-sm font-medium mb-3">SLA Alerts</h3>
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : !alerts?.length ? (
        <p className="text-sm text-muted-foreground">No active alerts</p>
      ) : (
        <div className="space-y-2">
          {alerts.map((alert) => (
            <div
              key={alert.id}
              className={`flex items-center justify-between p-2 rounded text-sm ${
                alert.severity === "critical"
                  ? "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"
                  : "bg-yellow-50 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-200"
              }`}
            >
              <div>
                <span className="font-medium">{alert.message}</span>
                {alert.stage_name && (
                  <span className="ml-2 text-xs opacity-70">{alert.stage_name}</span>
                )}
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => ack.mutate(alert.id)}
                disabled={ack.isPending}
              >
                Ack
              </Button>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
