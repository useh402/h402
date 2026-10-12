import { PageFade, ScrollProgress } from "@/components/smooth";

/** Wraps every page: a fade on each navigation and the reading progress line at the top. */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <PageFade>
      <ScrollProgress />
      {children}
    </PageFade>
  );
}
