"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useSkill, useSkillVersions, useCreateSkillVersion, usePromoteSkillVersion, useSkillTestResults } from "@/lib/queries/skills";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SkillDetailPage({ params }: { params: Promise<{ skillId: string }> }) {
  const { skillId } = use(params);
  const { data: skill } = useSkill(skillId);
  const { data: versions } = useSkillVersions(skillId);
  const { data: testResults } = useSkillTestResults(skillId);
  const createVersion = useCreateSkillVersion(skillId);
  const promote = usePromoteSkillVersion(skillId);

  const [showNewVersion, setShowNewVersion] = useState(false);
  const [instructions, setInstructions] = useState("");

  const handleCreateVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    await createVersion.mutateAsync({ instructions });
    setShowNewVersion(false);
    setInstructions("");
  };

  if (!skill) return <p className="p-8 text-muted-foreground">Loading...</p>;

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-4">
          <Link href="/skills" className="text-sm text-muted-foreground hover:text-foreground">&larr; Skills</Link>
          <h1 className="text-lg font-semibold">{skill.name}</h1>
          <Badge variant={skill.status === "active" ? "default" : "secondary"}>{skill.status}</Badge>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-6">
        <Card className="p-4">
          <div className="text-sm space-y-1">
            <p><span className="text-muted-foreground">Type:</span> {skill.skill_type}</p>
            <p><span className="text-muted-foreground">Target prompt:</span> {skill.target_prompt}</p>
            {skill.description && <p><span className="text-muted-foreground">Description:</span> {skill.description}</p>}
          </div>
        </Card>

        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Versions</h2>
          <Button size="sm" onClick={() => setShowNewVersion(!showNewVersion)}>
            {showNewVersion ? "Cancel" : "New Version"}
          </Button>
        </div>

        {showNewVersion && (
          <Card className="p-4">
            <form onSubmit={handleCreateVersion} className="space-y-3">
              <div>
                <label className="text-sm font-medium">Instructions</label>
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  className="w-full h-32 rounded border bg-background px-3 py-2 text-sm"
                  placeholder="Domain expert instructions for this skill..."
                  required
                />
              </div>
              <Button type="submit" disabled={createVersion.isPending}>
                {createVersion.isPending ? "Creating..." : "Create Version"}
              </Button>
            </form>
          </Card>
        )}

        {versions?.length ? (
          <div className="space-y-2">
            {versions.map((v) => (
              <Card key={v.id} className="p-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm">v{v.version_number}</span>
                    {v.is_active && <Badge>Active</Badge>}
                    {v.regression_passed === true && <Badge variant="secondary">Regression passed</Badge>}
                    {v.regression_passed === false && <Badge variant="destructive">Regression failed</Badge>}
                  </div>
                  {!v.is_active && (
                    <Button size="sm" variant="outline" onClick={() => promote.mutate(v.id)} disabled={promote.isPending}>
                      Promote
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{v.instructions}</p>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No versions yet</p>
        )}

        {testResults && testResults.length > 0 && (
          <>
            <h2 className="font-semibold">Test Results</h2>
            <div className="space-y-2">
              {testResults.map((r) => (
                <Card key={r.id} className="p-3 text-sm">
                  <div className="flex items-center gap-4">
                    <span>Accuracy: <strong>{((r.overall_accuracy ?? 0) * 100).toFixed(1)}%</strong></span>
                    {r.improvement_delta != null && (
                      <span className={r.improvement_delta >= 0 ? "text-green-600" : "text-red-600"}>
                        {r.improvement_delta >= 0 ? "+" : ""}{(r.improvement_delta * 100).toFixed(1)}%
                      </span>
                    )}
                    <span className="text-muted-foreground">{r.tested_at}</span>
                  </div>
                </Card>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
