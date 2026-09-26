"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

interface OverrideFormProps {
  currentValue: string | null;
  onSubmit: (value: string, reason: string) => void;
  onCancel: () => void;
  isPending: boolean;
}

export function OverrideForm({
  currentValue,
  onSubmit,
  onCancel,
  isPending,
}: OverrideFormProps) {
  const [value, setValue] = useState(currentValue ?? "");
  const [reason, setReason] = useState("");

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs text-muted-foreground">New value</label>
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          className="mt-1"
        />
      </div>
      <div>
        <label className="text-xs text-muted-foreground">Reason (required)</label>
        <Textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why are you overriding this value?"
          className="mt-1"
          rows={2}
        />
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => onSubmit(value, reason)}
          disabled={!value.trim() || !reason.trim() || isPending}
        >
          {isPending ? "Saving..." : "Save Override"}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
