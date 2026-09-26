"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { isAuthenticated } from "@/lib/api";
import { useKnowledge } from "@/lib/queries/skills";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Plus } from "lucide-react";

const ENTRY_TYPES = ["developer_profile", "lender_profile", "market_note", "deal_archetype", "deal_story"];

export default function KnowledgePage() {
  const router = useRouter();
  const [entryType, setEntryType] = useState<string | undefined>();
  const [search, setSearch] = useState("");
  const { data: entries, isLoading } = useKnowledge(entryType, search || undefined);

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
            <h1 className="text-lg font-semibold">Knowledge Library</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/skills" className="text-sm text-muted-foreground hover:text-foreground">Skills</Link>
            <Link href="/lenders" className="text-sm text-muted-foreground hover:text-foreground">Lenders</Link>
            <Link href="/knowledge/new">
              <Button size="sm"><Plus className="h-4 w-4 mr-1.5" />New Entry</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex gap-3 mb-4">
          <Input
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs"
          />
          <div className="flex gap-1">
            <button
              onClick={() => setEntryType(undefined)}
              className={`text-xs px-2 py-1 rounded ${!entryType ? "bg-primary text-primary-foreground" : "bg-muted"}`}
            >All</button>
            {ENTRY_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setEntryType(t)}
                className={`text-xs px-2 py-1 rounded ${entryType === t ? "bg-primary text-primary-foreground" : "bg-muted"}`}
              >{t.replace(/_/g, " ")}</button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : !entries?.length ? (
          <p className="text-sm text-muted-foreground">No entries yet</p>
        ) : (
          <div className="space-y-3">
            {entries.map((entry) => (
              <Link key={entry.id} href={`/knowledge/${entry.id}`}>
                <Card className="p-4 hover:bg-muted/50 cursor-pointer">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-medium">{entry.title}</h3>
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{entry.content}</p>
                      <div className="flex gap-1 mt-2">
                        {entry.tags?.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                        ))}
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0">{entry.entry_type.replace(/_/g, " ")}</Badge>
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
