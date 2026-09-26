"use client";

import { useAgentRunsPolling } from "@/lib/queries/agents";
import { ChevronDown, ChevronRight, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";

interface AgentRunStatusProps {
  dealId: string;
  agentName?: string;
  polling?: boolean;
}

export function AgentRunStatus({
  dealId,
  agentName,
  polling = false,
}: AgentRunStatusProps) {
  const { data: runs } = useAgentRunsPolling(dealId, polling);
  const [expandedRun, setExpandedRun] = useState<string | null>(null);
  const visibleRuns = agentName
    ? runs?.filter((run) => run.agent_name === agentName)
    : runs;

  if (!visibleRuns || visibleRuns.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">Agent Runs</h3>
      <div className="space-y-1">
        {visibleRuns.map((run) => {
          const isExpanded = expandedRun === run.id;
          const isRunning = run.status === "running";
          const isCompleted = run.status === "completed";
          const isFailed = run.status === "failed";

          return (
            <div key={run.id} className="border rounded-lg">
              <button
                className="w-full flex items-center gap-3 p-3 text-left hover:bg-muted/50"
                onClick={() => setExpandedRun(isExpanded ? null : run.id)}
              >
                {isRunning && <Loader2 className="h-4 w-4 animate-spin text-blue-500 shrink-0" />}
                {isCompleted && <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />}
                {isFailed && <XCircle className="h-4 w-4 text-red-500 shrink-0" />}

                <span className="text-sm font-medium flex-1">{run.agent_name}</span>

                <span className="text-xs text-muted-foreground">
                  {run.iterations} iter
                  {run.cost_usd ? ` | $${run.cost_usd.toFixed(4)}` : ""}
                </span>

                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                )}
              </button>

              {isExpanded && run.reasoning_trace && (
                <div className="border-t px-3 py-2 bg-muted/20 max-h-64 overflow-y-auto">
                  <div className="space-y-1">
                    {run.reasoning_trace.map((entry: Record<string, unknown>, i: number) => (
                      <div key={i} className="text-xs font-mono">
                        {entry.type === "text" && (
                          <p className="text-foreground">{String(entry.content).slice(0, 300)}</p>
                        )}
                        {entry.type === "tool_call" && (
                          <p className="text-blue-600">
                            tool: {String(entry.tool)}({JSON.stringify(entry.input).slice(0, 100)})
                          </p>
                        )}
                        {entry.type === "tool_result" && (
                          <p className={entry.success ? "text-green-600" : "text-red-600"}>
                            result: {String(entry.tool)} {entry.success ? "ok" : "error"}
                          </p>
                        )}
                        {entry.type === "thinking" && (
                          <p className="text-purple-600 italic">
                            thinking: {String(entry.content).slice(0, 200)}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                  {run.error && (
                    <div className="mt-2 text-xs text-red-600 border-t pt-2">
                      Error: {run.error}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {visibleRuns.length > 0 && (
        <div className="text-xs text-muted-foreground pt-1">
          Total cost: $
          {visibleRuns
            .reduce((sum, r) => sum + (r.cost_usd || 0), 0)
            .toFixed(4)}{" "}
          | Total tokens:{" "}
          {visibleRuns.reduce((sum, r) => sum + (r.input_tokens || 0) + (r.output_tokens || 0), 0).toLocaleString()}
        </div>
      )}
    </div>
  );
}
