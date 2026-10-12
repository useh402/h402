import { Suspense } from "react";
import type { Metadata } from "next";
import { EarnShell } from "@/components/earn/shell";

// The Earn area is a signed-in app rendered at runtime; opt it out of instant-navigation prerender checks.
export const instant = false;

export const metadata: Metadata = { title: "Earn — H402", description: "Take small tasks from real clients and get paid in stablecoins the moment the work is accepted." };

export default function EarnLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080808]" />}>
      <EarnShell>{children}</EarnShell>
    </Suspense>
  );
}
