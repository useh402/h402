import { Faq } from "@/components/faq";
import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";
import { Intro } from "@/components/intro";
import { Nav } from "@/components/nav";
import { Numbers } from "@/components/numbers";
import { Ticker } from "@/components/ticker";
import { Trust } from "@/components/trust";
import { TryTask } from "@/components/try-task";

export default function Page() {
  return (
    <main className="relative overflow-x-clip bg-[#080808]">
      <Nav />
      <Hero />
      <Ticker />
      <TryTask />
      <Intro />
      <Numbers />
      <Faq />
      <Trust />
      <Footer />
    </main>
  );
}
