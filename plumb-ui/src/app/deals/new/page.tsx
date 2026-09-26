"use client";

import Link from "next/link";
import { DealForm } from "@/components/upload/DealForm";
import { ArrowLeft } from "lucide-react";

export default function NewDealPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center gap-3">
          <Link
            href="/"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <h1 className="text-lg font-semibold">New Deal</h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        <DealForm />
      </main>
    </div>
  );
}
