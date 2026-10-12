import type { Metadata } from "next";

export const instant = false;

// The admin page: not for search engines, not linked from the site. Nothing on it loads without signing in.
export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false } };

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
