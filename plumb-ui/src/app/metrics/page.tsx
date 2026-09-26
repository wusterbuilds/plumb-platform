"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { isAuthenticated } from "@/lib/api";
import { useUser } from "@/hooks/useAuth";
import { VelocityChart } from "@/components/metrics/VelocityChart";
import { QualityTable } from "@/components/metrics/QualityTable";
import { CostBreakdown } from "@/components/metrics/CostBreakdown";
import { SlaStatus } from "@/components/metrics/SlaStatus";
import { BottleneckView } from "@/components/metrics/BottleneckView";

export default function MetricsPage() {
  const router = useRouter();
  const { data: user } = useUser();

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login");
  }, [router]);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/"><img src="/plumb-logo.png" alt="Plumb" className="h-9" /></Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-lg font-semibold">Metrics</h1>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/skills" className="text-muted-foreground hover:text-foreground">Skills</Link>
            <Link href="/knowledge" className="text-muted-foreground hover:text-foreground">Knowledge</Link>
            <Link href="/lenders" className="text-muted-foreground hover:text-foreground">Lenders</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <VelocityChart />
          <BottleneckView />
        </div>
        <SlaStatus />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <QualityTable />
          <CostBreakdown />
        </div>
      </main>
    </div>
  );
}
