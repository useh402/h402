import type { Metadata } from "next";

export const instant = false;
export const metadata: Metadata = { title: "Map — H402", description: "Every open task that has a place, on a globe." };

export default function MapLayout({ children }: { children: React.ReactNode }) {
  return children;
}
