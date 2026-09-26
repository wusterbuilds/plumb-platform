"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCreateKnowledge } from "@/lib/queries/skills";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

const ENTRY_TYPES = ["developer_profile", "lender_profile", "market_note", "deal_archetype", "deal_story"];

export default function NewKnowledgePage() {
  const router = useRouter();
  const create = useCreateKnowledge();
  const [entryType, setEntryType] = useState("market_note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tagsStr, setTagsStr] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const tags = tagsStr.split(",").map((t) => t.trim()).filter(Boolean);
    const result = await create.mutateAsync({ entry_type: entryType, title, content, tags });
    router.push(`/knowledge/${result.id}`);
  };

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/knowledge" className="text-sm text-muted-foreground hover:text-foreground">&larr; Knowledge</Link>
          <h1 className="text-lg font-semibold">New Entry</h1>
        </div>
      </header>
      <main className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium">Type</label>
              <select value={entryType} onChange={(e) => setEntryType(e.target.value)} className="w-full h-9 rounded border bg-background px-3 text-sm">
                {ENTRY_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Title</label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Extell Development" required />
            </div>
            <div>
              <label className="text-sm font-medium">Content</label>
              <textarea value={content} onChange={(e) => setContent(e.target.value)} className="w-full h-40 rounded border bg-background px-3 py-2 text-sm" placeholder="Structured knowledge content..." required />
            </div>
            <div>
              <label className="text-sm font-medium">Tags (comma-separated)</label>
              <Input value={tagsStr} onChange={(e) => setTagsStr(e.target.value)} placeholder="luxury_condo, manhattan, ground_up" />
            </div>
            <Button type="submit" disabled={!title || !content || create.isPending}>
              {create.isPending ? "Creating..." : "Create Entry"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
