"use client";

import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCurrencyFull, formatPercent, formatPerUnit } from "@/lib/format";
import type { BudgetLineItem } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronRight } from "lucide-react";

interface BudgetDetailTableProps {
  data: BudgetLineItem[];
}

const CATEGORY_ORDER = ["acquisition", "hard", "soft", "financing", "interest"];

const CATEGORY_LABELS: Record<string, string> = {
  acquisition: "Acquisition",
  hard: "Hard Costs",
  soft: "Soft Costs",
  financing: "Financing Costs",
  interest: "Interest Reserve",
};

export function BudgetDetailTable({ data }: BudgetDetailTableProps) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  // Group by category
  const grouped: Record<string, BudgetLineItem[]> = {};
  for (const item of data) {
    const cat = item.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  }

  const categories = CATEGORY_ORDER.filter((c) => grouped[c]?.length);

  const toggleCategory = (cat: string) => {
    setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  // Calculate category totals
  const categoryTotal = (items: BudgetLineItem[]) =>
    items.reduce((sum, item) => sum + item.total_cost, 0);
  const grandTotal = data.reduce((sum, item) => sum + item.total_cost, 0);

  return (
    <Table>
      <TableHeader>
        <TableRow className="bg-muted/50">
          <TableHead className="w-[240px]">Line Item</TableHead>
          <TableHead className="text-right">Total</TableHead>
          <TableHead className="text-right">% of TDC</TableHead>
          <TableHead className="text-right">Per ZFA</TableHead>
          <TableHead className="text-right">Per GSF</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {categories.map((cat) => {
          const items = grouped[cat];
          const isCollapsed = collapsed[cat];
          const total = categoryTotal(items);

          return (
            <tbody key={cat}>
              {/* Category header row */}
              <TableRow
                className="bg-muted/30 cursor-pointer hover:bg-muted/50"
                onClick={() => toggleCategory(cat)}
              >
                <TableCell className="font-semibold flex items-center gap-1">
                  {isCollapsed ? (
                    <ChevronRight className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronDown className="h-3.5 w-3.5" />
                  )}
                  {CATEGORY_LABELS[cat] ?? cat}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums font-semibold">
                  {formatCurrencyFull(total)}
                </TableCell>
                <TableCell className="text-right font-mono tabular-nums font-semibold">
                  {grandTotal > 0 ? formatPercent(total / grandTotal) : "—"}
                </TableCell>
                <TableCell />
                <TableCell />
              </TableRow>

              {/* Line items */}
              {!isCollapsed &&
                items.map((item, i) => (
                  <TableRow
                    key={item.label}
                    className={cn(i % 2 === 0 && "bg-muted/15")}
                  >
                    <TableCell className="pl-8">{item.label}</TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatCurrencyFull(item.total_cost)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatPercent(item.pct_total)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatPerUnit(item.per_zfa)}
                    </TableCell>
                    <TableCell className="text-right font-mono tabular-nums">
                      {formatPerUnit(item.per_gsf)}
                    </TableCell>
                  </TableRow>
                ))}
            </tbody>
          );
        })}

        {/* Grand Total */}
        <TableRow className="border-t-2 border-foreground/20 font-semibold bg-muted/50">
          <TableCell className="font-semibold">Total Development Cost</TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            {formatCurrencyFull(grandTotal)}
          </TableCell>
          <TableCell className="text-right font-mono tabular-nums">
            100.0%
          </TableCell>
          <TableCell />
          <TableCell />
        </TableRow>
      </TableBody>
    </Table>
  );
}
