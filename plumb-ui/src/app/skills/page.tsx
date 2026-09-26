"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { isAuthenticated } from "@/lib/api";
import { useSkills } from "@/lib/queries/skills";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus } from "lucide-react";

export default function SkillsPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<string | undefined>();
  const { data: skills, isLoading } = useSkills(filter);

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
            <h1 className="text-lg font-semibold">Skills</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/metrics" className="text-sm text-muted-foreground hover:text-foreground">Metrics</Link>
            <Link href="/knowledge" className="text-sm text-muted-foreground hover:text-foreground">Knowledge</Link>
            <Link href="/lenders" className="text-sm text-muted-foreground hover:text-foreground">Lenders</Link>
            <Link href="/skills/new">
              <Button size="sm"><Plus className="h-4 w-4 mr-1.5" />New Skill</Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        <div className="flex gap-2 mb-4">
          {[undefined, "draft", "active", "archived"].map((s) => (
            <button
              key={s ?? "all"}
              onClick={() => setFilter(s)}
              className={`text-sm px-3 py-1 rounded ${
                filter === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}
            >
              {s ?? "All"}
            </button>
          ))}
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : !skills?.length ? (
          <p className="text-sm text-muted-foreground">No skills yet. Create one to get started.</p>
        ) : (
          <div className="space-y-3">
            {skills.map((skill) => (
              <Link key={skill.id} href={`/skills/${skill.id}`}>
                <Card className="p-4 hover:bg-muted/50 cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium">{skill.name}</h3>
                      {skill.description && (
                        <p className="text-sm text-muted-foreground mt-1">{skill.description}</p>
                      )}
                      <div className="flex gap-2 mt-2">
                        <span className="text-xs text-muted-foreground">
                          {skill.skill_type} &middot; {skill.target_prompt}
                        </span>
                      </div>
                    </div>
                    <Badge variant={skill.status === "active" ? "default" : "secondary"}>
                      {skill.status}
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
