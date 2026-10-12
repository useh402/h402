"use client";

/** Pay a 402 from the browser with an EVM wallet (Robinhood Chain, Permit2). Solana browser payments come later. */

const PERMIT2 = "0x000000000022D473030F116dDEE9F6B43aC78BA3";
const PROXY = "0x402085c248EeA27D92E8b30b2C58ed07f9E20001";
const CHAINS: Record<string, { hex: string; name: string; rpc: string; explorer: string }> = {
  "eip155:4663": { hex: "0x1237", name: "Robinhood Chain", rpc: "https://rpc.mainnet.chain.robinhood.com", explorer: "https://robin.etherscan.io" },
  "eip155:46630": { hex: "0xb626", name: "Robinhood Chain Testnet", rpc: "https://rpc.testnet.chain.robinhood.com", explorer: "https://explorer.testnet.chain.robinhood.com" },
};

type Req = { scheme: string; network: string; asset: string; amount: string; payTo: string; maxTimeoutSeconds: number; extra?: Record<string, unknown> };
type Eth = { request: (a: { method: string; params?: unknown[] }) => Promise<unknown> };

function eth(): Eth {
  const e = (window as unknown as { ethereum?: Eth }).ethereum;
  if (!e) throw new Error("No EVM wallet found. Install MetaMask or Rabby.");
  return e;
}

const pad = (hex: string) => hex.replace(/^0x/, "").padStart(64, "0");
const toHex = (n: bigint) => "0x" + n.toString(16);

async function ensureChain(network: string) {
  const c = CHAINS[network];
  if (!c) throw new Error(`Unsupported network ${network}`);
  const current = (await eth().request({ method: "eth_chainId" })) as string;
  if (current.toLowerCase() === c.hex) return;
  try {
    await eth().request({ method: "wallet_switchEthereumChain", params: [{ chainId: c.hex }] });
  } catch {
    await eth().request({ method: "wallet_addEthereumChain", params: [{ chainId: c.hex, chainName: c.name, rpcUrls: [c.rpc], blockExplorerUrls: [c.explorer], nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 } }] });
  }
}

async function allowance(token: string, owner: string): Promise<bigint> {
  const data = "0xdd62ed3e" + pad(owner) + pad(PERMIT2);
  const r = (await eth().request({ method: "eth_call", params: [{ to: token, data }, "latest"] })) as string;
  return BigInt(r === "0x" ? 0 : r);
}

async function balance(token: string, owner: string): Promise<bigint> {
  const r = (await eth().request({ method: "eth_call", params: [{ to: token, data: "0x70a08231" + pad(owner) }, "latest"] })) as string;
  return BigInt(r === "0x" ? 0 : r);
}

async function approvePermit2(token: string, owner: string, onStatus: (s: string) => void) {
  onStatus("One-time approval: allowing Permit2 to move your tokens. Confirm in your wallet.");
  const max = "f".repeat(64);
  const tx = (await eth().request({ method: "eth_sendTransaction", params: [{ from: owner, to: token, data: "0x095ea7b3" + pad(PERMIT2) + max }] })) as string;
  onStatus("Approval sent. Waiting for it to confirm…");
  for (let i = 0; i < 90; i++) {
    const rc = (await eth().request({ method: "eth_getTransactionReceipt", params: [tx] })) as { status?: string } | null;
    if (rc) {
      if (rc.status === "0x1") return;
      throw new Error("The approval transaction failed.");
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  throw new Error("The approval is taking too long. Try again in a minute.");
}

function randomNonce(): string {
  const b = new Uint8Array(32);
  crypto.getRandomValues(b);
  return BigInt("0x" + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("")).toString();
}

/** Returns the base64 PAYMENT-SIGNATURE header value for the chosen requirement. */
export async function payWithEvmWallet(req: Req, onStatus: (s: string) => void = () => {}): Promise<string> {
  await ensureChain(req.network);
  const accounts = (await eth().request({ method: "eth_requestAccounts" })) as string[];
  const from = accounts[0];
  const amount = BigInt(req.amount);
  const bal = await balance(req.asset, from);
  if (bal < amount) throw new Error(`Not enough balance: you have ${(Number(bal) / 1e6).toFixed(2)} and the task costs ${(Number(amount) / 1e6).toFixed(2)}.`);
  if ((await allowance(req.asset, from)) < amount) await approvePermit2(req.asset, from, onStatus);
  onStatus("Sign the payment in your wallet. It costs no gas.");
  const chainId = parseInt(req.network.split(":")[1], 10);
  const nonce = randomNonce();
  const deadline = String(Math.floor(Date.now() / 1000) + (req.maxTimeoutSeconds || 300));
  const typed = {
    types: {
      EIP712Domain: [{ name: "name", type: "string" }, { name: "chainId", type: "uint256" }, { name: "verifyingContract", type: "address" }],
      PermitWitnessTransferFrom: [{ name: "permitted", type: "TokenPermissions" }, { name: "spender", type: "address" }, { name: "nonce", type: "uint256" }, { name: "deadline", type: "uint256" }, { name: "witness", type: "Witness" }],
      TokenPermissions: [{ name: "token", type: "address" }, { name: "amount", type: "uint256" }],
      Witness: [{ name: "to", type: "address" }, { name: "validAfter", type: "uint256" }],
    },
    primaryType: "PermitWitnessTransferFrom",
    domain: { name: "Permit2", chainId, verifyingContract: PERMIT2 },
    message: { permitted: { token: req.asset, amount: req.amount }, spender: PROXY, nonce, deadline, witness: { to: req.payTo, validAfter: "0" } },
  };
  const signature = (await eth().request({ method: "eth_signTypedData_v4", params: [from, JSON.stringify(typed)] })) as string;
  const payload = {
    x402Version: 2,
    accepted: req,
    payload: { signature, permit2Authorization: { from, permitted: { token: req.asset, amount: req.amount }, spender: PROXY, nonce, deadline, witness: { to: req.payTo, validAfter: "0" } } },
  };
  return btoa(JSON.stringify(payload));
}

export const explorerFor = (network: string) => CHAINS[network]?.explorer;
export { toHex };
