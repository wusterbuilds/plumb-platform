"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { formatCurrencyFull, formatPerUnit, formatNumber } from "@/lib/format";
import type { UnitMixTiered, UnitMixRow } from "@/lib/types";
import { cn } from "@/lib/utils";

interface UnitMixTableProps {
  data: UnitMixTiered;
}

const TIER_TABS = [
  { key: "fm" as const, label: "Free Market" },
  { key: "affordable_421a" as const, label: "421(a)" },
  { key: "mih" as const, label: "MIH" },
  { key: "commercial" as const, label: "Commercial" },
  { key: "total" as const, label: "Total" },
] as const;

function UnitMixRows({ rows }: { rows: UnitMixRow[] }) {
  if (rows.length === 0) {
    return (
      <TableRow>
        <TableCell colSpan={6} className="text-center text-muted-foreground py-6">
          No units in this tier
        </TableCell>
      </TableRow>
    );
  }

  return (
    <>
      {rows.map((row, i) => {
        const isTotal = row.beds === null && row.tier?.toLowerCase().includes("total");
        return (
          <TableRow
            key={`${row.tier}-${row.beds}-${i}`}
            className={cn(
              isTotal && "border-t-2 border-foreground/20 font-semibold bg-muted/50",
              !isTotal && i % 2 === 0 && "bg-muted/30",
            )}
          >
            <TableCell>
              {row.beds != null ? `${row.beds} BR` : row.tier}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {formatNumber(row.units)}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {formatNumber(row.sf_per_unit)}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {formatCurrencyFull(row.avg_monthly_rent)}
            </TableCell>
            <TableCell className="text-right font-mono tabular-nums">
              {formatPerUnit(row.rent_per_sf)}
            </TableCell>
          </TableRow>
        );
      })}
    </>
  );
}

export function UnitMixTable({ data }: UnitMixTableProps) {
  // Filter to tabs that have data
  const availableTabs = TIER_TABS.filter(
    (t) => data[t.key] && data[t.key].length > 0,
  );
  const defaultTab = availableTabs[0]?.key ?? "total";

  return (
    <Tabs defaultValue={defaultTab}>
      <TabsList variant="line">
        {availableTabs.map((t) => (
          <TabsTrigger key={t.key} value={t.key}>
            {t.label}
            <span className="ml-1 text-xs text-muted-foreground">
              ({data[t.key].length})
            </span>
          </TabsTrigger>
        ))}
      </TabsList>

      {availableTabs.map((t) => (
        <TabsContent key={t.key} value={t.key}>
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-[140px]">Type</TableHead>
                <TableHead className="text-right">Units</TableHead>
                <TableHead className="text-right">SF / Unit</TableHead>
                <TableHead className="text-right">Avg Rent</TableHead>
                <TableHead className="text-right">Rent / SF</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <UnitMixRows rows={data[t.key]} />
            </TableBody>
          </Table>
        </TabsContent>
      ))}
    </Tabs>
  );
}
