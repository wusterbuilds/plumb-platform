"use client";

import { useMemo, useState } from "react";
import { useOmNarratives } from "@/lib/queries/redlines";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Pencil } from "lucide-react";
import { RedlineDialog } from "./RedlineDialog";

interface OmEditModeProps {
  dealId: string;
  versionId: string;
}

interface SectionDescriptor {
  key: string;
  label: string;
  index: number | null;
  text: string;
  /** Optional second-line subhead shown above the body — comes from the
   * narrative's own `header` field (e.g. an investment-highlight title). */
  subhead?: string;
}

const SECTION_LABELS: Record<string, string> = {
  transaction_overview: "Transaction Overview",
  investment_highlights: "Investment Highlights",
  market_narrative: "Market Overview",
  sponsor_bios: "Sponsor",
};

export function OmEditMode({ dealId, versionId }: OmEditModeProps) {
  const { data, isLoading } = useOmNarratives(dealId, versionId);
  const [activeSection, setActiveSection] = useState<SectionDescriptor | null>(
    null,
  );

  const sections: SectionDescriptor[] = useMemo(() => {
    if (!data) return [];
    const out: SectionDescriptor[] = [];

    data.transaction_overview.forEach((para, idx) => {
      if (!para.trim()) return;
      out.push({
        key: "transaction_overview",
        label: `${SECTION_LABELS.transaction_overview} ¶${idx + 1}`,
        index: idx,
        text: para,
      });
    });

    data.investment_highlights.forEach((hl, idx) => {
      const body = hl.body ?? "";
      if (!body.trim()) return;
      out.push({
        key: "investment_highlights",
        label: `${SECTION_LABELS.investment_highlights} — ${hl.header ?? `#${idx + 1}`}`,
        index: idx,
        text: body,
        subhead: hl.header,
      });
    });

    data.market_narrative.forEach((sec, idx) => {
      const body = sec.body ?? "";
      if (!body.trim()) return;
      out.push({
        key: "market_narrative",
        label: `${SECTION_LABELS.market_narrative} — ${sec.header ?? `#${idx + 1}`}`,
        index: idx,
        text: body,
        subhead: sec.header,
      });
    });

    Object.entries(data.sponsor_bios).forEach(([name, paragraphs]) => {
      paragraphs.forEach((para, idx) => {
        if (!para.trim()) return;
        out.push({
          key: "sponsor_bios",
          label: `${SECTION_LABELS.sponsor_bios} — ${name} ¶${idx + 1}`,
          index: idx,
          text: para,
          subhead: name,
        });
      });
    });

    return out;
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading OM sections...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-sm text-muted-foreground py-12 text-center">
        No OM narrative content available for this version.
      </div>
    );
  }

  if (!sections.length) {
    return (
      <div className="text-sm text-muted-foreground py-12 text-center">
        This OM version has no editable narrative sections (likely an older
        version generated before structured snapshots existed).
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium">
            Editing v{data.version_number}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Hover any section and click <span className="font-medium">Suggest correction</span>{" "}
            to teach Plumb. Lessons apply to similar deals automatically.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data.archetype_signature && (
            <Badge variant="outline" className="font-mono text-[10px]">
              {data.archetype_signature}
            </Badge>
          )}
          <Badge variant="outline" className="text-xs">
            {data.redline_count} redline{data.redline_count === 1 ? "" : "s"}
          </Badge>
        </div>
      </div>

      <div className="space-y-3">
        {sections.map((s, i) => (
          <SectionCard
            key={`${s.key}-${s.index ?? "x"}-${i}`}
            section={s}
            onEdit={() => setActiveSection(s)}
          />
        ))}
      </div>

      {activeSection && (
        <RedlineDialog
          open={!!activeSection}
          onOpenChange={(open) => {
            if (!open) setActiveSection(null);
          }}
          dealId={dealId}
          versionId={versionId}
          sectionKey={activeSection.key}
          sectionLabel={activeSection.label}
          sectionIndex={activeSection.index}
          originalText={activeSection.text}
        />
      )}
    </div>
  );
}

function SectionCard({
  section,
  onEdit,
}: {
  section: SectionDescriptor;
  onEdit: () => void;
}) {
  return (
    <div className="group relative rounded-lg border p-4 transition-colors hover:border-foreground/30 hover:bg-muted/30">
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex flex-col">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {SECTION_LABELS[section.key] ?? section.key}
          </span>
          {section.subhead && (
            <span className="text-sm font-medium">{section.subhead}</span>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onEdit}
          className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
        >
          <Pencil className="h-3 w-3 mr-1.5" />
          Suggest correction
        </Button>
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/90">
        {section.text}
      </p>
    </div>
  );
}
