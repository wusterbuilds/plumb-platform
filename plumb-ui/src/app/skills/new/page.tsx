"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCreateSkill } from "@/lib/queries/skills";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";

const SKILL_TYPES = ["extraction", "narrative", "interpretation", "validation"];
const TARGET_PROMPTS = [
  "extract_pro_forma", "extract_project_summary", "extract_appraisal",
  "extract_sponsor", "extract_zoning", "extract_legal",
  "extract_market_research", "interpret_acris", "interpret_dob",
  "interpret_news",
];

export default function NewSkillPage() {
  const router = useRouter();
  const create = useCreateSkill();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [skillType, setSkillType] = useState("extraction");
  const [targetPrompt, setTargetPrompt] = useState("extract_pro_forma");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await create.mutateAsync({
      name, description: description || undefined,
      skill_type: skillType, target_prompt: targetPrompt,
    });
    router.push(`/skills/${result.id}`);
  };

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/skills" className="text-sm text-muted-foreground hover:text-foreground">&larr; Skills</Link>
          <h1 className="text-lg font-semibold">New Skill</h1>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Extract unit mix from luxury condo pro forma" required />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
            </div>
            <div>
              <label className="text-sm font-medium">Skill Type</label>
              <select value={skillType} onChange={(e) => setSkillType(e.target.value)} className="w-full h-9 rounded border bg-background px-3 text-sm">
                {SKILL_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Target Prompt</label>
              <select value={targetPrompt} onChange={(e) => setTargetPrompt(e.target.value)} className="w-full h-9 rounded border bg-background px-3 text-sm">
                {TARGET_PROMPTS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <Button type="submit" disabled={!name || create.isPending}>
              {create.isPending ? "Creating..." : "Create Skill"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
