"use client";

import { use, useState, useMemo, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useDeal } from "@/lib/queries/deals";
import {
  useExtractedValues,
  useReviewValue,
  useOverrideValue,
  useCrossReferences,
  useResolveCrossRef,
} from "@/lib/queries/extraction";
import { fieldGroupOrder } from "@/lib/field-groups";
import { FlagQueue, type QueueItem } from "@/components/review/FlagQueue";
import { FieldDetail } from "@/components/review/FieldDetail";
import { CrossRefView } from "@/components/review/CrossRefView";
import { SourceViewer } from "@/components/review/SourceViewer";
import { ReviewStatusBar } from "@/components/review/ReviewStatusBar";
import { useTriageKeyboard } from "@/components/review/useTriageKeyboard";
import { ArrowLeft } from "lucide-react";
import type { FlagColor } from "@/lib/types";

const FLAG_PRIORITY: Record<FlagColor, number> = { red: 0, yellow: 1, green: 2 };

export default function ExtractionReviewPage({
  params,
}: {
  params: Promise<{ dealId: string }>;
}) {
  const { dealId } = use(params);
  const router = useRouter();
  const { data: deal } = useDeal(dealId);
  const { data: valuesData } = useExtractedValues(dealId);
  const { data: crossRefsData } = useCrossReferences(dealId);

  const reviewValue = useReviewValue(dealId);
  const overrideValue = useOverrideValue(dealId);
  const resolveCrossRef = useResolveCrossRef(dealId);

  const [activeIndex, setActiveIndex] = useState(0);
  const [overrideMode, setOverrideMode] = useState(false);

  const allValues = valuesData?.values ?? [];
  const allCrossRefs = crossRefsData?.cross_references ?? [];

  // Build the queue: flagged fields sorted by priority, then cross-refs
  const queueItems: QueueItem[] = useMemo(() => {
    const flagged = allValues
      .filter((v) => v.flag !== "green" || v.reviewed_by != null)
      .sort((a, b) => {
        // Sort by flag priority first
        const flagDiff = FLAG_PRIORITY[a.flag] - FLAG_PRIORITY[b.flag];
        if (flagDiff !== 0) return flagDiff;
        // Then by field group
        return fieldGroupOrder(a.field_name) - fieldGroupOrder(b.field_name);
      });

    // Only include non-green, or green that were originally flagged (reviewed)
    const fieldItems: QueueItem[] = allValues
      .filter((v) => v.flag !== "green" || v.reviewed_by != null)
      .sort((a, b) => {
        const isAResolved = a.flag === "green";
        const isBResolved = b.flag === "green";
        if (isAResolved !== isBResolved) return isAResolved ? 1 : -1;
        const flagDiff = FLAG_PRIORITY[a.flag] - FLAG_PRIORITY[b.flag];
        if (flagDiff !== 0) return flagDiff;
        return fieldGroupOrder(a.field_name) - fieldGroupOrder(b.field_name);
      })
      .map((v) => ({
        type: "field" as const,
        id: v.id,
        fieldName: v.field_name,
        flag: v.flag,
        isResolved: v.flag === "green",
        value: v.override_value ?? v.value,
      }));

    const xrefItems: QueueItem[] = allCrossRefs
      .filter((x) => x.result === "mismatch")
      .map((x) => ({
        type: "crossref" as const,
        id: x.id,
        fieldName: `${x.field_a} vs ${x.field_b}`,
        flag: "yellow" as const,
        isResolved: !!x.resolution,
        value: x.delta,
      }));

    return [...fieldItems, ...xrefItems];
  }, [allValues, allCrossRefs]);

  const activeItem = queueItems[activeIndex];
  const activeField =
    activeItem?.type === "field"
      ? allValues.find((v) => v.id === activeItem.id)
      : null;
  const activeCrossRef =
    activeItem?.type === "crossref"
      ? allCrossRefs.find((x) => x.id === activeItem.id)
      : null;

  const resolvedCount = queueItems.filter((i) => i.isResolved).length;

  // Find next unresolved item
  const advanceToNext = useCallback(() => {
    setOverrideMode(false);
    const nextIdx = queueItems.findIndex(
      (item, idx) => idx > activeIndex && !item.isResolved,
    );
    if (nextIdx !== -1) {
      setActiveIndex(nextIdx);
    }
  }, [queueItems, activeIndex]);

  const handleConfirm = useCallback(() => {
    if (!activeField || overrideMode) return;
    reviewValue.mutate(activeField.id, { onSuccess: advanceToNext });
  }, [activeField, overrideMode, reviewValue, advanceToNext]);

  const handleOverride = useCallback(
    (value: string, reason: string) => {
      if (!activeField) return;
      overrideValue.mutate(
        {
          valueId: activeField.id,
          override_value: value,
          override_reason: reason,
          version: activeField.version,
        },
        { onSuccess: advanceToNext },
      );
    },
    [activeField, overrideValue, advanceToNext],
  );

  const handleSkip = useCallback(() => {
    advanceToNext();
  }, [advanceToNext]);

  const handleExit = useCallback(() => {
    if (overrideMode) {
      setOverrideMode(false);
    } else {
      router.push(`/deals/${dealId}`);
    }
  }, [overrideMode, router, dealId]);

  useTriageKeyboard({
    onNext: () =>
      setActiveIndex((i) => Math.min(i + 1, queueItems.length - 1)),
    onPrev: () => setActiveIndex((i) => Math.max(i - 1, 0)),
    onConfirm: handleConfirm,
    onOverride: () => setOverrideMode(true),
    onSkip: handleSkip,
    onExit: handleExit,
    enabled: !overrideMode,
  });

  if (!deal) return null;

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="border-b px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href={`/deals/${dealId}`}
            className="text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <span className="font-medium">Extraction Review</span>
            <span className="text-muted-foreground ml-2 text-sm">
              {deal.property_name || deal.property_address}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {queueItems.filter((i) => i.flag === "red" && !i.isResolved).length >
            0 && (
            <span className="text-red-600">
              {queueItems.filter((i) => i.flag === "red" && !i.isResolved).length}{" "}
              red
            </span>
          )}
          {queueItems.filter((i) => i.flag === "yellow" && !i.isResolved)
            .length > 0 && (
            <span className="text-amber-600">
              {queueItems.filter((i) => i.flag === "yellow" && !i.isResolved).length}{" "}
              yellow
            </span>
          )}
          <span className="text-green-600">{resolvedCount} done</span>
          <Link
            href={`/deals/${dealId}`}
            className="text-muted-foreground hover:text-foreground text-xs"
          >
            Exit Triage
          </Link>
        </div>
      </header>

      {/* Three-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Flag Queue */}
        <div className="w-56 border-r shrink-0">
          <FlagQueue
            items={queueItems}
            activeIndex={activeIndex}
            onSelect={setActiveIndex}
          />
        </div>

        {/* Center: Source Viewer */}
        <div className="flex-1 min-w-0">
          <SourceViewer
            dealId={dealId}
            docId={activeField?.source_doc_id ?? null}
            page={activeField?.source_page ?? null}
            snippet={activeField?.source_text_snippet ?? null}
          />
        </div>

        {/* Right: Field Detail or Cross-Ref */}
        <div className="w-80 border-l shrink-0 p-4 overflow-y-auto">
          {activeItem?.type === "field" && activeField && (
            <FieldDetail
              field={activeField}
              allValues={allValues}
              onConfirm={handleConfirm}
              onOverride={handleOverride}
              onSkip={handleSkip}
              isConfirming={reviewValue.isPending}
              isOverriding={overrideValue.isPending}
            />
          )}
          {activeItem?.type === "crossref" && activeCrossRef && (
            <CrossRefView
              crossRef={activeCrossRef}
              onResolve={(resolution) =>
                resolveCrossRef.mutate(
                  { xrefId: activeCrossRef.id, resolution },
                  { onSuccess: advanceToNext },
                )
              }
              isPending={resolveCrossRef.isPending}
            />
          )}
          {!activeItem && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No items to review
            </div>
          )}
        </div>
      </div>

      {/* Status bar */}
      <ReviewStatusBar
        current={activeIndex}
        total={queueItems.length}
        resolved={resolvedCount}
      />
    </div>
  );
}
