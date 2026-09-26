"use client";

import { use } from "react";
import Link from "next/link";
import { useKnowledgeEntry } from "@/lib/queries/skills";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function KnowledgeDetailPage({ params }: { params: Promise<{ entryId: string }> }) {
  const { entryId } = use(params);
  const { data: entry } = useKnowledgeEntry(entryId);

  if (!entry) return <p className="p-8 text-muted-foreground">Loading...</p>;

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-3xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/knowledge" className="text-sm text-muted-foreground hover:text-foreground">&larr; Knowledge</Link>
          <h1 className="text-lg font-semibold">{entry.title}</h1>
          <Badge variant="outline">{entry.entry_type.replace(/_/g, " ")}</Badge>
        </div>
      </header>
      <main className="max-w-3xl mx-auto px-4 py-6">
        <Card className="p-6">
          <div className="flex gap-1 mb-4">
            {entry.tags?.map((tag) => (
              <Badge key={tag} variant="secondary">{tag}</Badge>
            ))}
          </div>
          <div className="whitespace-pre-wrap text-sm">{entry.content}</div>
          <p className="text-xs text-muted-foreground mt-4">Created {entry.created_at}</p>
        </Card>
      </main>
    </div>
  );
}
