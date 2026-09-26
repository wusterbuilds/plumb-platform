"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCreateDeal } from "@/lib/queries/deals";
import { useUploadDocument } from "@/lib/queries/documents";
import { useStartExtraction } from "@/lib/queries/extraction";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FileDropzone } from "./FileDropzone";
import type { DealType } from "@/lib/types";

const DEAL_TYPES: { value: DealType; label: string }[] = [
  { value: "construction_loan", label: "Construction Loan" },
  { value: "stabilized_debt", label: "Stabilized Debt" },
  { value: "value_add", label: "Value-Add" },
  { value: "equity_placement", label: "Equity Placement" },
];

export function DealForm() {
  const router = useRouter();
  const createDeal = useCreateDeal();

  const [propertyName, setPropertyName] = useState("");
  const [address, setAddress] = useState("");
  const [dealType, setDealType] = useState<DealType>("construction_loan");
  const [capitalAsk, setCapitalAsk] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploading(true);

    try {
      // 1. Create the deal
      const deal = await createDeal.mutateAsync({
        deal_type: dealType,
        property_name: propertyName || undefined,
        property_address: address || undefined,
        capital_ask: "debt",
      });

      // 2. Upload each file
      for (let i = 0; i < files.length; i++) {
        setUploadProgress(`Uploading ${i + 1} of ${files.length}...`);
        const form = new FormData();
        form.append("file", files[i]);
        await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/deals/${deal.id}/documents`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${localStorage.getItem("plumb_token")}`,
            },
            body: form,
          },
        );
      }

      // 3. Start extraction
      setUploadProgress("Starting extraction...");
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/deals/${deal.id}/extraction/start`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("plumb_token")}`,
            "Content-Type": "application/json",
          },
        },
      );

      // 4. Navigate to workspace
      router.push(`/deals/${deal.id}`);
    } catch (err) {
      console.error("Failed to create deal:", err);
      setUploading(false);
      setUploadProgress("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6 max-w-lg">
      <div>
        <label className="text-sm font-medium">Property Name</label>
        <Input
          value={propertyName}
          onChange={(e) => setPropertyName(e.target.value)}
          placeholder="e.g. Harbor Point"
          className="mt-1"
        />
      </div>

      <div>
        <label className="text-sm font-medium">Address</label>
        <Input
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="e.g. 100 Harbor Way, Example City, NY"
          className="mt-1"
        />
      </div>

      <div>
        <label className="text-sm font-medium">Deal Type</label>
        <select
          value={dealType}
          onChange={(e) => setDealType(e.target.value as DealType)}
          className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          {DEAL_TYPES.map((dt) => (
            <option key={dt.value} value={dt.value}>
              {dt.label}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-sm font-medium">Capital Ask</label>
        <Input
          value={capitalAsk}
          onChange={(e) => setCapitalAsk(e.target.value)}
          placeholder="e.g. $180,000,000"
          className="mt-1"
        />
      </div>

      <div>
        <label className="text-sm font-medium">Documents</label>
        <div className="mt-1">
          <FileDropzone files={files} onFilesChange={setFiles} />
        </div>
      </div>

      <Button type="submit" disabled={uploading} className="w-full">
        {uploading ? uploadProgress || "Creating deal..." : "Create Deal & Start Processing"}
      </Button>
    </form>
  );
}
