"use client";

import { useRouter } from "next/navigation";
import { Panel, useWorker } from "@/components/earn/shell";
import { SignIn } from "@/components/sign-in";

export default function EarnHome() {
  const { refresh } = useWorker();
  const router = useRouter();
  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10">
      <div>
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70">
          <span className="h-[5px] w-[5px] bg-[#3b6cff]" />
          Earn
        </div>
        <h1 className="mt-5 font-serif text-[40px] font-light leading-[1.05] tracking-[-1px] sm:text-[64px] sm:tracking-[-2px]">
          Get paid for <em className="italic">judgment</em>.
        </h1>
        <p className="mt-6 max-w-[520px] font-serif text-[18px] font-light leading-[1.4] text-white/75">
          Small tasks are posted around the clock: check a receipt, pick the better option, read a sign, call a business, go and look, confirm something on a page. You do one in minutes. When the work is accepted, you are paid in stablecoins to the wallet you signed in with.
        </p>
        <ul className="mt-8 space-y-2 font-serif text-[16px] font-light text-white/60">
          <li>Connect MetaMask or Phantom. No account, no password.</li>
          <li>Paid in USDG on Robinhood Chain, from the contract, when you claim.</li>
          <li>A short qualification per type of work before real tasks. Good work builds your reputation and unlocks better-paid tasks.</li>
        </ul>
      </div>
      <Panel title="Connect your wallet">
        <SignIn
          role="worker"
          label="Connect wallet and start earning"
          onDone={async (w) => {
            await refresh();
            router.replace((w as { qualifiedTypes?: string[] }).qualifiedTypes?.length ? "/tasks" : "/earn/qualify/verify");
          }}
        />
      </Panel>
    </div>
  );
}
