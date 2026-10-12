import { API_URL } from "@/lib/api";

export const metadata = { title: "Connect your software — H402" };

const Code = ({ children }: { children: string }) => <pre className="overflow-auto rounded-[12px] border border-white/10 bg-black/50 p-4 font-mono text-[12.5px] leading-[1.5] text-white/85">{children}</pre>;

export default function Docs() {
  return (
    <div className="mx-auto max-w-[820px] space-y-10">
      <div>
        <h1 className="font-serif text-[44px] font-light leading-[1.05]">Connect your software</h1>
        <p className="mt-3 font-serif text-[17px] font-light leading-[1.45] text-white/70">
          Your software posts a task, gets back the exact price, pays with a wallet, and receives the answer by polling or by a signed webhook. There is no account to create: the wallet that pays is the client. Everything below is one endpoint and a few headers.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">1. Post a task</h2>
        <p className="font-serif text-[15px] text-white/65">Send the task. Without a payment you get a 402 with the price and a payment requirement for each chain.</p>
        <Code>{`POST ${API_URL}/v1/tasks
Content-Type: application/json

{
  "type": "do",
  "title": "Call the Walgreens on Market St and ask about pharmacy hours",
  "location": "San Francisco, CA",
  "acceptance": "Who answered, what they said, the time of the call",
  "payload": {
    "category": "calls",
    "instructions": "Call (415) 362-6363 during store hours. Ask until what time the pharmacy counter is open today. Write who answered, what they said and the time you called.",
    "proof": "text"
  },
  "pricePerWorker": 1500000,
  "timeLimitSeconds": 3600,
  "webhook": { "url": "https://your-server.example/h402" },
  "reference": "order-8841"
}

→ 402 Payment Required
PAYMENT-REQUIRED: <base64 of the x402 PaymentRequired object>
{ "quote": { "total": 1800000, "fee": 300000, "expiresAt": 1791540000 }, "x402": { "accepts": [ ... ] } }`}</Code>
        <p className="font-serif text-[14px] text-white/55">Amounts are in millionths of a dollar: 1500000 is $1.50. Types: do, verify, choose, rate, read, label, answer. Location is &quot;Remote&quot; or &quot;City, ST&quot; in the United States.</p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">2. Pay and post</h2>
        <p className="font-serif text-[15px] text-white/65">Sign the payment with your wallet and repeat the same request with the signature attached. The x402 client libraries do this in one call.</p>
        <Code>{`# Python (pip install x402[evm])
from x402 import x402Client
from x402.http.clients import wrapHttpxWithPayment
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import register_exact_evm_client
from eth_account import Account

client = x402Client()
client.set_spend_controls(False)
register_exact_evm_client(client, EthAccountSigner(Account.from_key(PRIVATE_KEY)), networks="eip155:4663")
async with wrapHttpxWithPayment(client) as http:
    r = await http.post("${API_URL}/v1/tasks", json=task)   # the 402 is handled for you
    task_id = r.json()["taskId"]
    buyer_token = r.json()["buyerToken"]`}</Code>
        <p className="font-serif text-[14px] text-white/55">The 202 response carries the task id, a result URL, a receipt URL and a buyer token. Keep the token: it is what lets your software accept, dispute or cancel that task later.</p>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">3. Get the answer</h2>
        <Code>{`GET ${API_URL}/v1/tasks/{taskId}

{ "state": "done", "result": { "answer": "yes", "votes": 3, "of": 3 }, "agreement": 1.0,
  "verification": { "method": "independent agreement (majority)", "outcome": "approved", "checks": [ ... ] } }

# Action tasks come back as "submitted" with a proof; accept it, or it is accepted after an hour
# (a proof with photos or a screenshot waits for the operator instead: "awaitingOperator": true)
POST ${API_URL}/v1/tasks/{taskId}/accept   { "buyerToken": "..." }
POST ${API_URL}/v1/tasks/{taskId}/accept   { "buyerToken": "...", "reject": true, "reason": "..." }
POST ${API_URL}/v1/tasks/{taskId}/cancel   { "buyerToken": "..." }        # before anyone answers
POST ${API_URL}/v1/tasks/{taskId}/dispute  { "buyerToken": "...", "reason": "..." }   # within 24 hours of done`}</Code>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">4. Webhooks</h2>
        <p className="font-serif text-[15px] text-white/65">Give a webhook URL in the task and we POST every state change there. The 202 response includes the secret for that task.</p>
        <Code>{`X-H402-Event: task.done
X-H402-Timestamp: 1791540000
X-H402-Signature: hex( HMAC-SHA256( secret, timestamp + "." + raw_body ) )
X-H402-Delivery: whd_...

{ "event": "task.done", "taskId": "task_...", "data": { ...same as GET /v1/tasks/{id}... } }

# Retried with backoff up to 8 times until you answer 2xx.`}</Code>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">5. Batches, pricing, receipts, templates</h2>
        <Code>{`POST ${API_URL}/v1/tasks/batch        { "tasks": [ ...up to 100... ] }   # one payment
GET  ${API_URL}/v1/pricing              # base prices, defaults, live worker availability
GET  ${API_URL}/v1/receipts/{taskId}    # public: payment, decision, payouts, refunds, ledger
GET  ${API_URL}/v1/catalogue            # categories of work
GET  ${API_URL}/v1/catalogue/templates  # 100 ready-made task templates, United States`}</Code>
      </section>

      <section className="space-y-3">
        <h2 className="font-serif text-[26px] font-light">Rules</h2>
        <ul className="list-disc space-y-1 pl-5 font-serif text-[15px] text-white/65">
          <li>Never include passwords, codes, keys or payment details. Such tasks are refused and refunded.</li>
          <li>Tasks that ask a person to buy, pay, or act as someone else are held for review first.</li>
          <li>Nothing about private individuals. Businesses, places and public listings only.</li>
          <li>Money is held before anyone starts and released when the work is accepted. Unfilled slots are refunded.</li>
        </ul>
      </section>
    </div>
  );
}
