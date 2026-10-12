"use client";

import { useRouter } from "next/navigation";
import { Panel } from "@/components/earn/shell";
import { useClient } from "@/components/client/shell";
import { SignIn } from "@/components/sign-in";

export default function ClientHome() {
  const { refresh } = useClient();
  const router = useRouter();
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10">
      <div>
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />For clients</div>
        <h1 className="mt-5 font-serif text-[38px] font-light leading-[1.05] tracking-[-1px] sm:text-[60px] sm:tracking-[-2px]">Your software, <em className="italic">a real person</em>.</h1>
        <p className="mt-6 max-w-[520px] font-serif text-[18px] font-light leading-[1.4] text-white/75">
          Tasks here are posted by software, not by hand: the platform posts its own work around the clock, and your systems can post theirs through the API. A qualified person in the United States does the work in minutes. Payment is held before anyone starts and released only when the work is accepted. Sign in with the wallet your software pays from to follow its tasks.
        </p>
        <ul className="mt-8 space-y-2 font-serif text-[16px] font-light text-white/60">
          <li>Short tasks are answered by three people and paid only when they agree.</li>
          <li>Action tasks come back with proof. You accept it, or dispute it, within an hour.</li>
          <li>Every task has a public receipt: what was paid, who was paid, how it was decided.</li>
          <li>Posting is by API only. See Connect your software.</li>
        </ul>
      </div>
      <Panel title="Sign in">
        <SignIn
          role="client"
          onDone={async () => {
            await refresh();
            router.replace("/client/tasks");
          }}
        />
      </Panel>
    </div>
  );
}
