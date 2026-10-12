import type { Metadata } from "next";

export const instant = false;

// The operator's page: not for search engines, not linked from the site. Nothing on it loads without the operator key.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
