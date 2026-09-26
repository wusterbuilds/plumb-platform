"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isAuthenticated } from "@/lib/api";
import { useUser, useLogout } from "@/hooks/useAuth";
import { DealList } from "@/components/inbox/DealList";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export default function InboxPage() {
  const router = useRouter();
  const { data: user } = useUser();
  const logout = useLogout();

  useEffect(() => {
    if (!isAuthenticated()) router.push("/login");
  }, [router]);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 h-14 flex items-center justify-between">
          <img src="/plumb-logo.png" alt="Plumb" className="h-9" />
          <div className="flex items-center gap-3">
            <Link href="/metrics" className="text-sm text-muted-foreground hover:text-foreground">Metrics</Link>
            <Link href="/skills" className="text-sm text-muted-foreground hover:text-foreground">Skills</Link>
            <Link href="/knowledge" className="text-sm text-muted-foreground hover:text-foreground">Knowledge</Link>
            <Link href="/lenders" className="text-sm text-muted-foreground hover:text-foreground">Lenders</Link>
            <Link href="/deals/new">
              <Button size="sm">
                <Plus className="h-4 w-4 mr-1.5" />
                New Deal
              </Button>
            </Link>
            {user && (
              <button
                onClick={logout}
                className="text-sm text-muted-foreground hover:text-foreground"
              >
                {user.name}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-6">
        <DealList />
      </main>
    </div>
  );
}
