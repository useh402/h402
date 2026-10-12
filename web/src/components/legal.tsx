import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";

export function Legal({ label, title, updated, children }: { label: string; title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[820px] px-6 pb-24 pt-[110px] sm:pt-[140px]">
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />{label}</div>
        <h1 className="mt-4 font-serif text-[36px] font-light leading-[1.06] tracking-[-1px] sm:text-[52px]">{title}</h1>
        <p className="mt-3 font-serif text-[13px] text-white/45">Last updated {updated}</p>
        <div className="legal mt-10 space-y-6 font-serif text-[16px] font-light leading-[1.55] text-white/80 [&_h2]:mt-10 [&_h2]:font-serif [&_h2]:text-[22px] [&_h2]:font-light [&_h2]:text-white [&_li]:ml-5 [&_li]:list-disc">{children}</div>
      </main>
      <Footer />
    </div>
  );
}
