"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCreateLender } from "@/lib/queries/lenders";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

const LENDER_TYPES = ["bank", "debt_fund", "insurance", "agency", "mezz", "bridge"];

export default function NewLenderPage() {
  const router = useRouter();
  const create = useCreateLender();
  const [name, setName] = useState("");
  const [lenderType, setLenderType] = useState("bank");
  const [notes, setNotes] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await create.mutateAsync({ name, lender_type: lenderType, notes: notes || undefined });
    router.push(`/lenders/${result.id}`);
  };

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/lenders" className="text-sm text-muted-foreground hover:text-foreground">&larr; Lenders</Link>
          <h1 className="text-lg font-semibold">New Lender</h1>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Goldman Sachs Realty Finance" required />
            </div>
            <div>
              <label className="text-sm font-medium">Type</label>
              <select value={lenderType} onChange={(e) => setLenderType(e.target.value)} className="w-full h-9 rounded border bg-background px-3 text-sm">
                {LENDER_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Notes</label>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full h-24 rounded border bg-background px-3 py-2 text-sm" placeholder="Optional notes" />
            </div>
            <Button type="submit" disabled={!name || create.isPending}>
              {create.isPending ? "Creating..." : "Create Lender"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
