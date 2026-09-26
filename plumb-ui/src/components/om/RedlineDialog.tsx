"use client";

import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { useCreateRedline } from "@/lib/queries/redlines";
import type {
  RedlineCategory,
  RedlineSeverity,
} from "@/lib/types";

interface RedlineDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  dealId: string;
  versionId: string;
  sectionKey: string;
  sectionLabel: string;
  sectionIndex: number | null;
  originalText: string;
}

const CATEGORIES: { value: RedlineCategory; label: string }[] = [
  { value: "factual_error", label: "Factual error" },
  { value: "aggressive_assumption", label: "Aggressive assumption" },
  { value: "omission", label: "Missing detail" },
  { value: "tone", label: "Tone / positioning" },
  { value: "compliance", label: "Compliance / legal" },
  { value: "positioning", label: "Pitch framing" },
];

const SEVERITIES: { value: RedlineSeverity; label: string }[] = [
  { value: "minor", label: "Minor" },
  { value: "moderate", label: "Moderate" },
  { value: "material", label: "Material" },
];

export function RedlineDialog({
  open,
  onOpenChange,
  dealId,
  versionId,
  sectionKey,
  sectionLabel,
  sectionIndex,
  originalText,
}: RedlineDialogProps) {
  const [edited, setEdited] = useState(originalText);
  const [category, setCategory] = useState<RedlineCategory>("factual_error");
  const [severity, setSeverity] = useState<RedlineSeverity>("moderate");
  const [rationale, setRationale] = useState("");
  const create = useCreateRedline(dealId, versionId);

  useEffect(() => {
    if (open) {
      setEdited(originalText);
      setRationale("");
      setCategory("factual_error");
      setSeverity("moderate");
      create.reset();
    }
    // We intentionally only re-init when the dialog opens or the original
    // text changes — re-running on every keystroke would clobber the user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, originalText]);

  const unchanged = edited.trim() === originalText.trim();

  const handleSave = () => {
    if (unchanged) return;
    create.mutate(
      {
        section_key: sectionKey,
        section_index: sectionIndex,
        original_text: originalText,
        edited_text: edited,
        rationale: rationale.trim() || null,
        correction_category: category,
        severity,
      },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        // The Dialog primitive's default content class includes `sm:max-w-sm`,
        // which wins over a non-prefixed `max-w-*` at the `sm` breakpoint.
        // Use the `sm:` prefix so our wider value actually applies.
        className="sm:max-w-2xl gap-4"
        style={{ maxHeight: "90vh", overflowY: "auto" }}
      >
        <DialogHeader>
          <DialogTitle>Suggest correction</DialogTitle>
          <DialogDescription>
            <span className="inline-flex items-center gap-2">
              <span>Section:</span>
              <Badge variant="outline" className="font-mono text-xs">
                {sectionLabel}
              </Badge>
            </span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <label className="text-xs uppercase tracking-wider text-muted-foreground">
              Original
            </label>
            <div className="mt-1 rounded-md border bg-muted/40 px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap">
              {originalText}
            </div>
          </div>

          <div>
            <label
              htmlFor="redline-edited"
              className="text-xs uppercase tracking-wider text-muted-foreground"
            >
              Your version
            </label>
            <Textarea
              id="redline-edited"
              value={edited}
              onChange={(e) => setEdited(e.target.value)}
              rows={6}
              className="mt-1 text-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="redline-category"
                className="text-xs uppercase tracking-wider text-muted-foreground"
              >
                Category
              </label>
              <select
                id="redline-category"
                value={category}
                onChange={(e) =>
                  setCategory(e.target.value as RedlineCategory)
                }
                className="mt-1 w-full rounded-md border bg-transparent px-2.5 py-2 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="redline-severity"
                className="text-xs uppercase tracking-wider text-muted-foreground"
              >
                Severity
              </label>
              <select
                id="redline-severity"
                value={severity}
                onChange={(e) =>
                  setSeverity(e.target.value as RedlineSeverity)
                }
                className="mt-1 w-full rounded-md border bg-transparent px-2.5 py-2 text-sm"
              >
                {SEVERITIES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label
              htmlFor="redline-rationale"
              className="text-xs uppercase tracking-wider text-muted-foreground"
            >
              Reason (optional, but ideal — Plumb learns from this)
            </label>
            <Textarea
              id="redline-rationale"
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              rows={3}
              placeholder="e.g. Williamsburg Class A condo comps run $1,800–$2,100/SF, not the $2,400–$2,600/SF the model wrote."
              className="mt-1 text-sm"
            />
          </div>

          {create.isError && (
            <div className="text-sm text-destructive">
              Could not save redline: {(create.error as Error)?.message}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={create.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={create.isPending || unchanged}
          >
            {create.isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                Saving...
              </>
            ) : (
              "Save redline"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
