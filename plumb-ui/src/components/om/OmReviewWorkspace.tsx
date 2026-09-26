"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OmPreview } from "./OmPreview";
import { OmEditMode } from "./OmEditMode";
import { OmCompareView } from "./OmCompareView";
import { RedlinePanel } from "./RedlinePanel";
import { OmStatus } from "./OmStatus";
import { useOmVersions } from "@/lib/queries/om";

interface OmReviewWorkspaceProps {
  dealId: string;
}

/**
 * Orchestrates the OM review experience:
 *
 *   ┌──────────────────────────────────────┬─────────────────┐
 *   │ Tabs: View · Edit · Compare          │  Redline panel  │
 *   │                                       │  (always shown  │
 *   │  PDF iframe / styled cards / diff    │   when there is │
 *   │                                       │   a version)    │
 *   └──────────────────────────────────────┴─────────────────┘
 *
 * The redline panel sits side-by-side with the active tab so the reviewer
 * always sees what's been captured and can hit "Re-run with feedback"
 * without losing their place in the document.
 */
export function OmReviewWorkspace({ dealId }: OmReviewWorkspaceProps) {
  const { data: versions } = useOmVersions(dealId);
  const latestReady = versions?.versions.find((v) => v.status === "ready");
  const [tab, setTab] = useState<string>("view");

  return (
    <div className="space-y-3">
      <OmStatus dealId={dealId} />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="min-w-0">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList variant="line">
              <TabsTrigger value="view">View PDF</TabsTrigger>
              <TabsTrigger value="edit">Edit / Redline</TabsTrigger>
              <TabsTrigger value="compare">Compare versions</TabsTrigger>
            </TabsList>

            <TabsContent value="view" className="mt-4">
              <OmPreview dealId={dealId} showStatus={false} />
            </TabsContent>

            <TabsContent value="edit" className="mt-4">
              {latestReady ? (
                <OmEditMode dealId={dealId} versionId={latestReady.id} />
              ) : (
                <div className="text-sm text-muted-foreground py-12 text-center">
                  No OM version is ready to edit yet.
                </div>
              )}
            </TabsContent>

            <TabsContent value="compare" className="mt-4">
              <OmCompareView dealId={dealId} />
            </TabsContent>
          </Tabs>
        </div>

        <div className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)]">
          {latestReady ? (
            <RedlinePanel dealId={dealId} versionId={latestReady.id} />
          ) : (
            <div className="rounded-lg border border-dashed py-12 px-4 text-center text-xs text-muted-foreground">
              Generate an OM to start capturing expert feedback.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
