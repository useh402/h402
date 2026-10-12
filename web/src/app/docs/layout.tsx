import type { Metadata } from "next";

export const instant = false;
export const metadata: Metadata = { title: "Docs — H402", description: "How H402 works: tasks, proof, rewards, the contract, the API and the rules." };

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
