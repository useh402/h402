"use client";

import { PrivyProvider, type PrivyClientConfig } from "@privy-io/react-auth";
import { MotionConfig } from "framer-motion";
import { AutoTranslate } from "@/lib/auto-translate";
import { LangProvider } from "@/lib/i18n";
import { SmoothScroll } from "./smooth";

const APP_ID = process.env.NEXT_PUBLIC_PRIVY_APP_ID ?? "";
export const PRIVY_ON = APP_ID.length > 0;

type Chain = NonNullable<PrivyClientConfig["defaultChain"]>;
const chain = (id: number, name: string, rpc: string, explorer: string): Chain =>
  ({ id, name, nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 }, rpcUrls: { default: { http: [rpc] } }, blockExplorers: { default: { name: "Explorer", url: explorer } } }) as Chain;

const robinhood = chain(4663, "Robinhood Chain", "https://rpc.mainnet.chain.robinhood.com", "https://robinhoodchain.blockscout.com");
const robinhoodTestnet = chain(46630, "Robinhood Chain Testnet", "https://rpc.testnet.chain.robinhood.com", "https://explorer.testnet.chain.robinhood.com");
// Phantom only works on a fixed set of networks and refuses to switch to any other. Signing in is just a signed
// message, so these are accepted for sign-in; rewards are still paid on Robinhood Chain to the same address.
const signInOnly = [
  chain(1, "Ethereum", "https://ethereum-rpc.publicnode.com", "https://etherscan.io"),
  chain(8453, "Base", "https://mainnet.base.org", "https://basescan.org"),
  chain(137, "Polygon", "https://polygon-rpc.com", "https://polygonscan.com"),
  chain(11155111, "Sepolia", "https://ethereum-sepolia-rpc.publicnode.com", "https://sepolia.etherscan.io"),
];

export function Providers({ children }: { children: React.ReactNode }) {
  // Every animation honours the reader's reduced-motion setting, and the page glides under inertia scrolling.
  const inner = (
    <LangProvider>
      <AutoTranslate />
      <MotionConfig reducedMotion="user">
        <SmoothScroll>{children}</SmoothScroll>
      </MotionConfig>
    </LangProvider>
  );
  if (!PRIVY_ON) return inner;
  return (
    <PrivyProvider
      appId={APP_ID}
      config={{
        loginMethods: ["wallet"],
        appearance: { theme: "dark", accentColor: "#3b6cff", landingHeader: "Connect your wallet", loginMessage: "Your rewards are paid to the wallet you connect.", walletList: ["metamask", "phantom"], walletChainType: "ethereum-only" },
        embeddedWallets: { ethereum: { createOnLogin: "off" } },
        defaultChain: signInOnly[0],
        supportedChains: [...signInOnly, robinhood, robinhoodTestnet],
      }}
    >
      {inner}
    </PrivyProvider>
  );
}
