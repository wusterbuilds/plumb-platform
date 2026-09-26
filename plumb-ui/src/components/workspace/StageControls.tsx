"use client";

import { useState } from "react";
import { useTransitionDeal } from "@/lib/queries/deals";
import { useExtractionStatus } from "@/lib/queries/extraction";
import { useExcelDownload } from "@/lib/queries/financial";
import { useOmStatus } from "@/lib/queries/om";
import { useOmDownloadUrl } from "@/lib/queries/om";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import type { Deal, DealStatus } from "@/lib/types";

const NEXT_STAGE: Partial<Record<DealStatus, DealStatus>> = {
  extraction_review: "market_enrichment",
  om_review: "lender_outreach",
};

const SEND_BACK_TARGETS: Partial<Record<DealStatus, DealStatus[]>> = {
  om_review: ["extraction_review", "om_drafting"],
  model_building: ["extraction_review"],
};

interface StageControlsProps {
  deal: Deal;
}

export function StageControls({ deal }: StageControlsProps) {
  const transition = useTransitionDeal(deal.id);
  const { data: extraction } = useExtractionStatus(deal.id);
  const [sendBackTarget, setSendBackTarget] = useState<DealStatus | null>(null);
  const [reason, setReason] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [holdDialogOpen, setHoldDialogOpen] = useState(false);
  const [holdReason, setHoldReason] = useState("");

  const excel = useExcelDownload(deal.id);
  const { data: omStatus } = useOmStatus(deal.id);
  const latestVersionId = omStatus?.latest_version?.id;
  const omDownload = useOmDownloadUrl(deal.id, latestVersionId ?? "");

  const nextStage = NEXT_STAGE[deal.status];
  const sendBackOptions = SEND_BACK_TARGETS[deal.status] ?? [];

  // Gate check: can't release from extraction_review if red/yellow flags remain
  const redCount = extraction?.fields_by_flag?.red ?? 0;
  const yellowCount = extraction?.fields_by_flag?.yellow ?? 0;
  const canRelease =
    deal.status !== "extraction_review" || (redCount === 0 && yellowCount === 0);

  const showDownloads =
    deal.status === "om_review" ||
    deal.status === "lender_outreach" ||
    deal.status === "tracking" ||
    deal.status === "term_sheet_received" ||
    deal.status === "closed";

  return (
    <div className="space-y-2">
      {/* Download buttons for post-model stages */}
      {showDownloads && (
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={excel.download}
          >
            <FileSpreadsheet className="h-3.5 w-3.5 mr-1.5" />
            Excel
          </Button>
          {latestVersionId && (
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={omDownload.download}
            >
              <FileText className="h-3.5 w-3.5 mr-1.5" />
              OM PDF
            </Button>
          )}
        </div>
      )}

      {/* Release to next stage */}
      {nextStage && (
        <Button
          className="w-full"
          onClick={() =>
            transition.mutate({ target_status: nextStage, reason: "Released by user" })
          }
          disabled={!canRelease || transition.isPending}
        >
          {!canRelease
            ? `Resolve all flags first`
            : `Release to ${nextStage.replace(/_/g, " ")}`}
        </Button>
      )}

      {/* Send back */}
      {sendBackOptions.length > 0 && (
        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogTrigger
            render={<Button variant="outline" className="w-full" size="sm" />}
          >
            Send Back
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Send deal back</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="flex gap-2">
                {sendBackOptions.map((target) => (
                  <Button
                    key={target}
                    variant={sendBackTarget === target ? "default" : "outline"}
                    size="sm"
                    onClick={() => setSendBackTarget(target)}
                  >
                    {target.replace(/_/g, " ")}
                  </Button>
                ))}
              </div>
              <Textarea
                placeholder="Reason for sending back..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
              <Button
                disabled={!sendBackTarget || !reason.trim() || transition.isPending}
                onClick={() => {
                  if (sendBackTarget) {
                    transition.mutate(
                      { target_status: sendBackTarget, reason },
                      { onSuccess: () => setDialogOpen(false) },
                    );
                  }
                }}
              >
                Confirm
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}

      {/* Hold / Kill */}
      <div className="flex gap-2">
        <Dialog open={holdDialogOpen} onOpenChange={setHoldDialogOpen}>
          <DialogTrigger
            render={<Button variant="outline" size="sm" className="flex-1" />}
          >
            Hold
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Put deal on hold</DialogTitle>
            </DialogHeader>
            <Textarea
              placeholder="Reason..."
              value={holdReason}
              onChange={(e) => setHoldReason(e.target.value)}
            />
            <Button
              disabled={!holdReason.trim() || transition.isPending}
              onClick={() => {
                transition.mutate(
                  { target_status: "on_hold", reason: holdReason },
                  { onSuccess: () => setHoldDialogOpen(false) },
                );
              }}
            >
              Confirm
            </Button>
          </DialogContent>
        </Dialog>

        <Button
          variant="destructive"
          size="sm"
          className="flex-1"
          onClick={() => {
            if (confirm("Kill this deal? This cannot be undone.")) {
              transition.mutate({
                target_status: "dead",
                reason: "Killed by user",
                dead_reason: "other",
              });
            }
          }}
        >
          Kill
        </Button>
      </div>
    </div>
  );
}
