"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { isAuthenticated } from "@/lib/api";
import { useLenders } from "@/lib/queries/lenders";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Plus } from "lucide-react";

const LENDER_TYPE_LABELS: Record<string, string> = {
  bank: "Bank",
  debt_fund: "Debt Fund",
  insurance: "Insurance",
  agency: "Agency",
  mezz: "Mezz",
  bridge: "Bridge",
};

export default function LendersPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { data: lenders, isLoading } = useLenders(search || undefined);

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login");
  }, [router]);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/"><img src="/plumb-logo.png" alt="Plumb" className="h-9" /></Link>
            <span className="text-muted-foreground">/</span>
            <h1 className="text-lg font-semibold">Lenders</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/metrics" className="text-sm text-muted-foreground hover:text-foreground">Metrics</Link>
            <Link href="/skills" className="text-sm text-muted-foreground hover:text-foreground">Skills</Link>
            <Link href="/knowledge" className="text-sm text-muted-foreground hover:text-foreground">Knowledge</Link>
            <Link href="/lenders/new">
              <Button size="sm"><Plus className="h-4 w-4 mr-1.5" />New Lender</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        <Input
          placeholder="Search lenders..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs mb-4"
        />

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : !lenders?.length ? (
          <p className="text-sm text-muted-foreground">No lenders yet. Add one to start tracking appetite.</p>
        ) : (
          <div className="space-y-2">
            {lenders.map((lender) => (
              <Link key={lender.id} href={`/lenders/${lender.id}`}>
                <Card className="p-4 hover:bg-muted/50 cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium">{lender.name}</h3>
                      {lender.notes && (
                        <p className="text-sm text-muted-foreground mt-1 line-clamp-1">{lender.notes}</p>
                      )}
                    </div>
                    <Badge variant="outline">
                      {LENDER_TYPE_LABELS[lender.lender_type] || lender.lender_type}
                    </Badge>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
