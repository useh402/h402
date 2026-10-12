import { Suspense } from "react";
import type { Metadata } from "next";
import { ClientShell } from "@/components/client/shell";

export const instant = false;
export const metadata: Metadata = { title: "Clients — H402", description: "Post a task, pay a fixed price, get a verified human answer in minutes." };

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080808]" />}>
      <ClientShell>{children}</ClientShell>
    </Suspense>
  );
}
