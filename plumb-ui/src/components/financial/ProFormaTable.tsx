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
import type { RentalProForma, ProFormaLine } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ProFormaTableProps {
  data: RentalProForma;
}

function PfRow({ line, even }: { line: ProFormaLine; even?: boolean }) {
  return (
    <TableRow
      className={cn(
        line.is_subtotal &&
          "border-t-2 border-foreground/20 font-semibold bg-muted/50",
        !line.is_subtotal && even && "bg-muted/30",
      )}
    >
      <TableCell className={cn(line.is_subtotal && "font-semibold")}>
        {line.label}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPerUnit(line.per_sf)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPerUnit(line.per_unit_yr)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatPercent(line.pct_of_egi)}
      </TableCell>
      <TableCell className="text-right font-mono tabular-nums">
        {formatCurrencyFull(line.total)}
      </TableCell>
    </TableRow>
  );
}

export function ProFormaTable({ data }: ProFormaTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/50">
          <TableHead className="w-[240px]">Line Item</TableHead>
          <TableHead className="text-right">Per SF</TableHead>
          <TableHead className="text-right">Per Unit/Yr</TableHead>
          <TableHead className="text-right">% of EGI</TableHead>
          <TableHead className="text-right">Total</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {/* Income section */}
        <TableRow className="bg-muted/20">
          <TableCell
            colSpan={5}
            className="text-xs font-semibold uppercase tracking-wider text-muted-foreground py-1"
          >
            Revenue
          </TableCell>
        </TableRow>
        {data.income_lines.map((line, i) => (
          <PfRow key={line.label} line={line} even={i % 2 === 0} />
        ))}
        <PfRow line={data.egi} />

        {/* Expenses section */}
        <TableRow className="bg-muted/20">
          <TableCell
            colSpan={5}
            className="text-xs font-semibold uppercase tracking-wider text-muted-foreground py-1"
          >
            Operating Expenses
          </TableCell>
        </TableRow>
        {data.expense_lines.map((line, i) => (
          <PfRow key={line.label} line={line} even={i % 2 === 0} />
        ))}
        <PfRow line={data.total_expenses} />

        {/* NOI */}
        <TableRow className="border-t-2 border-foreground/30 font-bold bg-muted/60">
          <TableCell className="font-bold">{data.noi.label}</TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            {formatPerUnit(data.noi.per_sf)}
          </TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            {formatPerUnit(data.noi.per_unit_yr)}
          </TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            {formatPercent(data.noi.pct_of_egi)}
          </TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            {formatCurrencyFull(data.noi.total)}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  );
}
