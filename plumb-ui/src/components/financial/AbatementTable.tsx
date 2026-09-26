"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatCurrencyFull,
  formatCurrencyCompact,
  formatPercent,
  formatPercentPrecise,
  formatNumber,
} from "@/lib/format";
import type { AbatementSchedule } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface AbatementTableProps {
  data: AbatementSchedule;
}

export function AbatementTable({ data }: AbatementTableProps) {
  const chartData = data.years.map((yr) => ({
    year: yr.year,
    savings: yr.ret_savings,
    unabated: yr.unabated_ret,
    abated: yr.abated_ret,
  }));

  return (
    <div className="space-y-6">
      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Program
          </p>
          <p className="text-lg font-semibold mt-1">
            421(a) Option {data.program_option}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            NPV of Tax Savings
          </p>
          <p className="text-lg font-semibold font-mono tabular-nums mt-1">
            {formatCurrencyCompact(data.npv_of_tax_savings)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Assessment Growth
          </p>
          <p className="text-lg font-semibold font-mono tabular-nums mt-1">
            {formatPercentPrecise(data.assessment_growth_rate)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            Discount Rate
          </p>
          <p className="text-lg font-semibold font-mono tabular-nums mt-1">
            {formatPercentPrecise(data.discount_rate)}
          </p>
        </div>
      </div>

      {/* Chart */}
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="year"
              className="text-xs"
              tick={{ fontSize: 11 }}
            />
            <YAxis
              className="text-xs"
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => formatCurrencyCompact(v)}
            />
            <Tooltip
              formatter={(value) => formatCurrencyFull(value as number)}
              labelFormatter={(label) => `Year ${label}`}
            />
            <Line
              type="monotone"
              dataKey="savings"
              name="RET Savings"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="unabated"
              name="Unabated RET"
              stroke="#ef4444"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
            />
            <Line
              type="monotone"
              dataKey="abated"
              name="Abated RET"
              stroke="#3b82f6"
              strokeWidth={1}
              strokeDasharray="4 4"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Year-by-year table */}
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead>Year</TableHead>
            <TableHead className="text-right">% Exempt</TableHead>
            <TableHead className="text-right">Unabated RET</TableHead>
            <TableHead className="text-right">Abated RET</TableHead>
            <TableHead className="text-right">Savings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.years.map((yr, i) => (
            <TableRow
              key={yr.year}
              className={cn(i % 2 === 0 && "bg-muted/30")}
            >
              <TableCell>{yr.year}</TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {formatPercent(yr.pct_exempt)}
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {formatCurrencyFull(yr.unabated_ret)}
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {formatCurrencyFull(yr.abated_ret)}
              </TableCell>
              <TableCell className="text-right font-mono tabular-nums">
                {formatCurrencyFull(yr.ret_savings)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
