"use client";

import { useEffect, useState } from "react";
import { usePrivy, useWallets } from "@privy-io/react-auth";
import { api, getToken, RAILS } from "@/lib/api";
import { PRIVY_ON } from "@/components/providers";

const USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168";
const CHAIN = { id: 4663, hex: "0x1237", name: "Robinhood Chain", rpc: "https://rpc.mainnet.chain.robinhood.com", explorer: "https://robinhoodchain.blockscout.com" };
type Eip1193 = { request: (args: { method: string; params?: unknown[] }) => Promise<unknown> };

const rpc = async (method: string, params: unknown[]) => {
  const r = await fetch(CHAIN.rpc, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }) });
  const j = await r.json();
  if (j.error) throw new Error(j.error.message);
  return j.result as string;
};
const pad = (hex: string) => hex.toLowerCase().replace("0x", "").padStart(64, "0");
const fmt = (atomic: bigint, decimals: number, places = 2) => {
  const s = atomic.toString().padStart(decimals + 1, "0");
  return `${s.slice(0, -decimals)}.${s.slice(-decimals, -decimals + places)}`;
};

/** Moves a worker's USDG out of the wallet it was paid to. The platform covers the gas once a day for wallets it has paid. */
export function Withdraw({ wallet, rail }: { wallet: string; rail: string }) {
  const [usdg, setUsdg] = useState<bigint | null>(null);
  const [eth, setEth] = useState<bigint | null>(null);
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState<"gas" | "send" | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string; tx?: string } | null>(null);
  const mainnet = RAILS.robinhood.network === "eip155:4663";

  const refresh = async () => {
    try {
      const [u, e] = await Promise.all([rpc("eth_call", [{ to: USDG, data: "0x70a08231" + pad(wallet) }, "latest"]), rpc("eth_getBalance", [wallet, "latest"])]);
      setUsdg(BigInt(u));
      setEth(BigInt(e));
    } catch {
      // the chain is unreachable; keep the last figures
    }
  };
  useEffect(() => {
    if (rail !== "robinhood" || !mainnet) return;
    const first = setTimeout(refresh, 0);
    const id = setInterval(refresh, 15_000);
    return () => {
      clearTimeout(first);
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wallet, rail]);

  if (rail !== "robinhood" || !mainnet) return null;
  const needsGas = eth !== null && eth < BigInt(6_000_000_000_000); // under 0.000006 ETH: not enough for one transfer

  const coverGas = async () => {
    setBusy("gas");
    setMsg(null);
    try {
      const r = await api<{ granted: boolean; transaction: string | null; reason?: string }>("/v1/workers/gas", { body: {} });
      setMsg(r.granted ? { ok: true, text: "Gas covered. You can send now.", tx: r.transaction ?? undefined } : { ok: true, text: r.reason ?? "This wallet already has enough gas." });
      setTimeout(refresh, 4000);
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <WithProvider>
      {(provider) => (
        <div className="rounded-[16px] border border-white/[0.08] bg-white/[0.025] p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 className="font-serif text-[20px] font-light">Withdraw</h2>
            <div className="font-serif text-[13px] text-white/55">
              In this wallet: <span className="font-mono text-white">{usdg === null ? "…" : fmt(usdg, 6)} USDG</span>
              <span className="ml-3">Gas: <span className={`font-mono ${needsGas ? "text-amber-200" : "text-white"}`}>{eth === null ? "…" : fmt(eth, 18, 6)} ETH</span></span>
            </div>
          </div>
          <p className="mt-2 font-serif text-[14px] font-light text-white/55">
            Rewards sit in your wallet as USDG on Robinhood Chain. Sending them anywhere needs a little ETH for gas. {needsGas ? "Your wallet has none, so the platform covers it." : "You have enough for a transfer."}
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_160px]">
            <input value={to} onChange={(e) => setTo(e.target.value.trim())} placeholder="Destination address, 0x…" className="h-[46px] rounded-[12px] border border-white/10 bg-black/30 px-4 font-mono text-[14px] text-white outline-none placeholder:text-white/30" />
            <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={usdg !== null ? `up to ${fmt(usdg, 6)}` : "amount"} inputMode="decimal" className="h-[46px] rounded-[12px] border border-white/10 bg-black/30 px-4 font-mono text-[14px] text-white outline-none placeholder:text-white/30" />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            {needsGas && (
              <button onClick={coverGas} disabled={busy !== null} className="h-[44px] rounded-full border border-white/30 px-5 font-serif text-[15px] text-white hover:bg-white/[0.06] disabled:opacity-50">
                {busy === "gas" ? "Covering gas…" : "1. Cover the gas"}
              </button>
            )}
            <button
              disabled={busy !== null || needsGas || !/^0x[0-9a-fA-F]{40}$/.test(to) || !(Number(amount) > 0) || usdg === null || !provider}
              onClick={async () => {
                if (!provider) return;
                setBusy("send");
                setMsg(null);
                try {
                  const atomic = BigInt(Math.round(Number(amount) * 1e6));
                  if (atomic > usdg!) throw new Error("That is more than the wallet holds.");
                  try {
                    await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN.hex }] });
                  } catch {
                    await provider.request({ method: "wallet_addEthereumChain", params: [{ chainId: CHAIN.hex, chainName: CHAIN.name, rpcUrls: [CHAIN.rpc], nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 }, blockExplorerUrls: [CHAIN.explorer] }] });
                  }
                  const data = "0xa9059cbb" + pad(to) + atomic.toString(16).padStart(64, "0");
                  const tx = (await provider.request({ method: "eth_sendTransaction", params: [{ from: wallet, to: USDG, data }] })) as string;
                  setMsg({ ok: true, text: `Sent ${amount} USDG.`, tx });
                  setAmount("");
                  setTimeout(refresh, 6000);
                } catch (e) {
                  setMsg({ ok: false, text: (e as { message?: string })?.message?.slice(0, 160) || "The wallet did not send it." });
                } finally {
                  setBusy(null);
                }
              }}
              className="h-[44px] rounded-full bg-white px-6 font-serif text-[15px] font-semibold text-[#0a0a0f] hover:bg-[#e6ecff] disabled:opacity-40"
            >
              {busy === "send" ? "Waiting for your wallet…" : needsGas ? "2. Send USDG" : "Send USDG"}
            </button>
          </div>
          {msg && (
            <p className={`mt-3 font-serif text-[14px] ${msg.ok ? "text-[#9be36b]" : "text-red-300"}`}>
              {msg.text}
              {msg.tx && <a href={`${CHAIN.explorer}/tx/${msg.tx}`} target="_blank" rel="noreferrer" className="ml-2 text-[#9db4ff] underline">view transaction ↗</a>}
            </p>
          )}
          {!getToken() && <p className="mt-2 font-serif text-[13px] text-white/40">Sign in to use this.</p>}
        </div>
      )}
    </WithProvider>
  );
}

/** Hands the wallet's provider to its child: from Privy when it is on, else the browser wallet. */
function WithProvider({ children }: { children: (p: Eip1193 | null) => React.ReactNode }) {
  return PRIVY_ON ? <PrivyProvider>{children}</PrivyProvider> : <>{children((typeof window !== "undefined" ? (window as unknown as { ethereum?: Eip1193 }).ethereum : null) ?? null)}</>;
}

function PrivyProvider({ children }: { children: (p: Eip1193 | null) => React.ReactNode }) {
  const { authenticated } = usePrivy();
  const { wallets } = useWallets();
  const [provider, setProvider] = useState<Eip1193 | null>(null);
  useEffect(() => {
    let live = true;
    const w = wallets[0];
    const t = setTimeout(() => {
      if (!authenticated || !w) {
        setProvider(null);
        return;
      }
      w.getEthereumProvider().then((p) => {
        if (live) setProvider(p as unknown as Eip1193);
      });
    }, 0);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [authenticated, wallets]);
  return <>{children(provider)}</>;
}


