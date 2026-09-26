"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrencyFull, formatPercent, formatPerUnit } from "@/lib/format";
import type { SourcesUses, SourcesUsesLine } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SourcesUsesTableProps {
  data: SourcesUses;
}

function SuRow({
  line,
  isTotal,
  even,
}: {
  line: SourcesUsesLine;
  isTotal?: boolean;
  even?: boolean;
}) {
  return (
    <TableRow
      className={cn(
        isTotal && "border-t-2 border-foreground/20 font-semibold bg-muted/50",
        !isTotal && even && "bg-muted/30",
      )}
    >
      <TableCell className={cn(isTotal && "font-semibold")}>
        {line.label}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatCurrencyFull(line.total)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPercent(line.pct_total)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPerUnit(line.per_zfa)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPerUnit(line.per_gsf)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPerUnit(line.per_nra)}
      </TableCell>
    </TableRow>
  );
}

export function SourcesUsesTable({ data }: SourcesUsesTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/50">
          <TableHead className="w-[200px]">Category</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="text-right">% of TDC</TableHead>
          <TableHead className="text-right">Per ZFA</TableHead>
          <TableHead className="text-right">Per GSF</TableHead>
          <TableHead className="text-right">Per NRA</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {/* Sources */}
        <TableRow className="bg-muted/20">
          <TableCell
            colSpan={6}
            className="text-xs font-semibold uppercase tracking-wider text-muted-foreground py-1"
          >
            Sources
          </TableCell>
        </TableRow>
        {data.sources.map((line, i) => (
          <SuRow key={line.label} line={line} even={i % 2 === 0} />
        ))}
        <SuRow line={data.total_sources} isTotal />

        {/* Uses */}
        <TableRow className="bg-muted/20">
          <TableCell
            colSpan={6}
            className="text-xs font-semibold uppercase tracking-wider text-muted-foreground py-1"
          >
            Uses
          </TableCell>
        </TableRow>
        {data.uses.map((line, i) => (
          <SuRow key={line.label} line={line} even={i % 2 === 0} />
        ))}
        <SuRow line={data.total_uses} isTotal />
      </TableBody>
    </Table>
  );
}
