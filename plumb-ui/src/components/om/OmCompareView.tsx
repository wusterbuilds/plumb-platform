"use client";

import { useMemo, useState } from "react";
import { useOmVersions } from "@/lib/queries/om";
import { useOmNarratives, useRedlines } from "@/lib/queries/redlines";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";

interface OmCompareViewProps {
  dealId: string;
}

interface FlatSection {
  key: string;
  index: number | null;
  text: string;
  subhead?: string;
}

const SECTION_LABELS: Record<string, string> = {
  transaction_overview: "Transaction Overview",
  investment_highlights: "Investment Highlights",
  market_narrative: "Market Overview",
  sponsor_bios: "Sponsor",
};

function flatten(narrative: ReturnType<typeof useOmNarratives>["data"]): FlatSection[] {
  if (!narrative) return [];
  const out: FlatSection[] = [];
  narrative.transaction_overview.forEach((p, i) => {
    if (p?.trim()) out.push({ key: "transaction_overview", index: i, text: p });
  });
  narrative.investment_highlights.forEach((h, i) => {
    if (h.body?.trim())
      out.push({
        key: "investment_highlights",
        index: i,
        text: h.body,
        subhead: h.header,
      });
  });
  narrative.market_narrative.forEach((s, i) => {
    if (s.body?.trim())
      out.push({
        key: "market_narrative",
        index: i,
        text: s.body,
        subhead: s.header,
      });
  });
  Object.entries(narrative.sponsor_bios).forEach(([name, paragraphs]) => {
    paragraphs.forEach((p, i) => {
      if (p?.trim())
        out.push({ key: "sponsor_bios", index: i, text: p, subhead: name });
    });
  });
  return out;
}

function pickSection(
  flat: FlatSection[],
  key: string,
  index: number | null,
  subhead?: string,
): FlatSection | null {
  // section_index is the canonical match key; subhead is a tiebreaker for
  // sponsor bios (which are keyed by sponsor name rather than ordinal).
  if (key === "sponsor_bios" && subhead) {
    return (
      flat.find(
        (s) =>
          s.key === key &&
          s.subhead === subhead &&
          (index === null || s.index === index),
      ) ?? null
    );
  }
  return (
    flat.find((s) => s.key === key && s.index === index) ?? null
  );
}

export function OmCompareView({ dealId }: OmCompareViewProps) {
  const { data: versions } = useOmVersions(dealId);
  const ready = versions?.versions.filter((v) => v.status !== "generating") ?? [];

  // Default to comparing latest ready against the previous ready version.
  const latest = ready[0];
  const previous = ready[1];
  const [leftId, setLeftId] = useState<string | null>(null);
  const [rightId, setRightId] = useState<string | null>(null);
  const effectiveLeftId = leftId ?? previous?.id ?? null;
  const effectiveRightId = rightId ?? latest?.id ?? null;

  const { data: leftNar } = useOmNarratives(dealId, effectiveLeftId);
  const { data: rightNar } = useOmNarratives(dealId, effectiveRightId);
  const { data: redlinesData } = useRedlines(dealId, effectiveLeftId);

  const leftFlat = useMemo(() => flatten(leftNar), [leftNar]);
  const rightFlat = useMemo(() => flatten(rightNar), [rightNar]);

  if (!ready || ready.length < 2) {
    return (
      <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
        Need two OM versions to compare. Capture a redline and click{" "}
        <span className="font-medium">Re-run with feedback</span> to generate
        the second version.
      </div>
    );
  }

  if (!leftNar || !rightNar) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin mr-2" />
        Loading versions...
      </div>
    );
  }

  // The interesting sections to surface are the ones that were redlined in
  // the left version. If no redlines (e.g. comparing an arbitrary pair) fall
  // back to all sections that differ.
  const redlines = redlinesData?.redlines ?? [];
  const focusKeys: { key: string; index: number | null; subhead?: string }[] =
    redlines.length > 0
      ? redlines.map((r) => ({
          key: r.section_key,
          index: r.section_index,
          subhead:
            r.section_key === "sponsor_bios"
              ? // Best-effort — section_index alone isn't unique for sponsor
                // bios, but the redline didn't capture the sponsor name. The
                // demo path doesn't redline sponsor bios.
                undefined
              : undefined,
        }))
      : leftFlat
          .filter((l) => {
            const r = pickSection(rightFlat, l.key, l.index, l.subhead);
            return r && r.text.trim() !== l.text.trim();
          })
          .map((l) => ({ key: l.key, index: l.index, subhead: l.subhead }));

  const lessonsApplied =
    rightNar && effectiveRightId && versions
      ? // pull from applied_episodes via /narratives if present; we don't
        // currently surface that. Defer to a later iteration.
        []
      : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Compare</span>
          <select
            value={effectiveLeftId ?? ""}
            onChange={(e) => setLeftId(e.target.value)}
            className="rounded-md border bg-transparent px-2 py-1 text-sm"
          >
            {ready.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
          <ArrowRight className="h-3 w-3 text-muted-foreground" />
          <select
            value={effectiveRightId ?? ""}
            onChange={(e) => setRightId(e.target.value)}
            className="rounded-md border bg-transparent px-2 py-1 text-sm"
          >
            {ready.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
        </div>

        {redlines.length > 0 && (
          <div className="text-xs text-muted-foreground">
            Showing sections redlined in v{leftNar.version_number}
          </div>
        )}
      </div>

      {focusKeys.length === 0 ? (
        <div className="rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground">
          No section-level differences detected between these versions.
        </div>
      ) : (
        <div className="space-y-4">
          {focusKeys.map((f, i) => {
            const left = pickSection(leftFlat, f.key, f.index, f.subhead);
            const right = pickSection(rightFlat, f.key, f.index, f.subhead);
            if (!left && !right) return null;
            return (
              <div key={`${f.key}-${i}`} className="rounded-lg border">
                <div className="px-4 py-2 border-b bg-muted/30 flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    {SECTION_LABELS[f.key] ?? f.key}
                  </Badge>
                  {(left?.subhead || right?.subhead) && (
                    <span className="text-xs font-medium">
                      {right?.subhead ?? left?.subhead}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2">
                  <div className="p-4 border-r bg-rose-50/40">
                    <p className="text-[10px] uppercase tracking-wider text-rose-700 mb-2">
                      v{leftNar.version_number} (before)
                    </p>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {left?.text ?? <em className="text-muted-foreground">(missing)</em>}
                    </p>
                  </div>
                  <div className="p-4 bg-emerald-50/40">
                    <p className="text-[10px] uppercase tracking-wider text-emerald-700 mb-2 inline-flex items-center gap-1">
                      <Sparkles className="h-2.5 w-2.5" />
                      v{rightNar.version_number} (after feedback)
                    </p>
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {right?.text ?? <em className="text-muted-foreground">(missing)</em>}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {lessonsApplied.length > 0 && (
        <div className="rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-900">
          {lessonsApplied.length} lesson{lessonsApplied.length === 1 ? "" : "s"} applied to v
          {rightNar.version_number}
        </div>
      )}
    </div>
  );
}
