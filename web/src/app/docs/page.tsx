import Link from "next/link";
import { Nav } from "@/components/nav";
import { Footer } from "@/components/footer";
import { Reveal } from "@/components/motion";

const CONTRACT = "0x530C2beDB048a658cB9fFD074eB7A75D68bfBd90";
const EXPLORER = `https://robinhoodchain.blockscout.com/address/${CONTRACT}?tab=contract`;

const SECTIONS = [
  ["what", "What H402 is"],
  ["life", "The life of a task"],
  ["start", "Start earning"],
  ["types", "Types of work"],
  ["photos", "Proof photos"],
  ["rewards", "Rewards and claiming"],
  ["rules", "Rules for workers"],
  ["clients", "For clients"],
  ["money", "Payments and the contract"],
  ["operator", "For operators"],
  ["privacy", "Privacy and training"],
  ["faq", "Questions"],
] as const;

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-[#080808] text-white">
      <Nav />
      <main className="mx-auto max-w-[1400px] px-4 pb-24 pt-[100px] sm:px-8 sm:pt-[130px]">
        <div className="flex items-center gap-2.5 font-serif text-[14px] text-white/70"><span className="h-[5px] w-[5px] bg-[#3b6cff]" />Documentation</div>
        <h1 className="mt-4 font-serif text-[38px] font-light leading-[1.06] tracking-[-1px] sm:text-[56px] sm:tracking-[-2px]">How H402 <em className="italic">works</em>.</h1>
        <p className="mt-5 max-w-[720px] font-serif text-[17px] font-light leading-[1.5] text-white/65">
          Everything a worker, a client or an operator needs: how tasks are posted and decided, how proof works, how rewards are paid from the contract, and the rules. Written from the platform as it runs today.
        </p>

        <div className="mt-12 grid gap-10 lg:grid-cols-[240px_1fr]">
          <nav className="lg:sticky lg:top-[110px] lg:self-start">
            <ol className="flex gap-2 overflow-x-auto whitespace-nowrap pb-2 lg:flex-col lg:gap-0 lg:whitespace-normal lg:pb-0">
              {SECTIONS.map(([id, label], i) => (
                <li key={id}>
                  <a href={`#${id}`} className="block rounded-full border border-white/10 px-3 py-1.5 font-serif text-[14px] text-white/70 hover:text-white lg:rounded-none lg:border-0 lg:border-l lg:border-white/10 lg:px-4 lg:py-2 lg:hover:border-white/50">
                    <span className="mr-2 font-mono text-[11px] text-white/35">{String(i + 1).padStart(2, "0")}</span>{label}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <article className="docs min-w-0 max-w-[820px] space-y-16 font-serif text-[16px] font-light leading-[1.6] text-white/80 [&_h2]:font-serif [&_h2]:text-[30px] [&_h2]:font-light [&_h2]:leading-[1.1] [&_h2]:text-white [&_h3]:mt-8 [&_h3]:font-serif [&_h3]:text-[20px] [&_h3]:text-white [&_p]:mt-4 [&_li]:mt-2 [&_ol]:mt-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_ul]:mt-4 [&_ul]:list-disc [&_ul]:pl-6 [&_table]:mt-5 [&_table]:w-full [&_table]:text-[15px] [&_td]:border-t [&_td]:border-white/10 [&_td]:py-2.5 [&_td]:pr-4 [&_td]:align-top [&_th]:pb-2 [&_th]:pr-4 [&_th]:text-left [&_th]:font-mono [&_th]:text-[11px] [&_th]:uppercase [&_th]:tracking-[0.06em] [&_th]:text-white/45 [&_code]:rounded [&_code]:bg-white/[0.07] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[13px] [&_code]:text-white [&_strong]:font-normal [&_strong]:text-white">
            <Reveal y={14}><section id="what">
              <h2>1. What H402 is</h2>
              <p>H402 is a board of small pieces of work that need a real person: a call to make, a place to go and photograph, a page that blocks software, a judgement several people have to agree on. Tasks are posted by the platform and by software connected to it, never by hand, each with a fixed reward. A person takes a task, does it, and is paid in USDG on Robinhood Chain once the work is accepted.</p>
              <p>Three things never change: the reward is fixed before anyone starts; a reward is paid only after acceptance and only to the wallet that did the work; and every payment is a transaction anyone can look up.</p>
              <p>Tasks are for people in the United States.</p>
            </section></Reveal>

            <Reveal y={14}><section id="life">
              <h2>2. The life of a task</h2>
              <ol>
                <li><strong>Listed.</strong> The task appears on the <Link href="/tasks" className="underline">board</Link> with its reward, its type, the place if it has one, and how many people it needs. Listing costs nothing.</li>
                <li><strong>Taken.</strong> A qualified worker takes it. The reward is locked in the contract at that moment. A quick task is held for 15 minutes; an action task for 30.</li>
                <li><strong>Answered.</strong> The worker submits an answer, a written proof, or photos. Every response is saved.</li>
                <li><strong>Decided.</strong> Quick tasks are decided by agreement between the people who answered. Proof tasks are checked by automated review and, when needed, by an operator.</li>
                <li><strong>Claimed.</strong> An accepted worker presses Claim. The contract pays the reward to their wallet in one transaction and sets the fee aside.</li>
                <li><strong>Closed.</strong> A task nobody finishes is refunded in full to the pool. Content is removed thirty days after a task is decided.</li>
              </ol>
            </section></Reveal>

            <Reveal y={14}><section id="start">
              <h2>3. Start earning</h2>
              <ol>
                <li><strong>Connect a wallet.</strong> MetaMask or Phantom, from the button at the top right. There is no account and no password; a signed message is your sign-in, and the wallet is where rewards are paid.</li>
                <li><strong>Accept the worker terms.</strong> Once, on the <Link href="/earn" className="underline">Earn</Link> page.</li>
                <li><strong>Qualify for a type of work.</strong> Each type has three practice questions. Two right unlocks paid tasks of that type. You can retry at any time and go back to change an answer.</li>
                <li><strong>Take a task</strong> from the board or the map. Read the requirements on the task page first; they say exactly what is accepted.</li>
                <li><strong>Answer</strong> within the time shown. Quick tasks take a minute; action tasks need a written note, a screenshot or camera photos.</li>
                <li><strong>Claim.</strong> When the answer is accepted, a Claim reward button appears on the task page and on your Earnings page.</li>
              </ol>
              <p>Your <Link href="/earn/earnings" className="underline">Earnings</Link> page shows rewards ready to claim, what was paid, every transaction, and a Withdraw panel for moving USDG on. If your wallet has no ETH for gas, the platform covers one transfer a day for wallets it has paid.</p>
            </section></Reveal>

            <Reveal y={14}><section id="types">
              <h2>4. Types of work</h2>
              <table>
                <thead><tr><th>Type</th><th>What you do</th><th>Decided by</th><th>Typical reward</th></tr></thead>
                <tbody>
                  <tr><td>Check</td><td>Answer yes, no or unsure about text or a picture</td><td>Agreement of 2 or 3 people</td><td>$1 to $3</td></tr>
                  <tr><td>Choose</td><td>Pick the best of two to five options</td><td>Majority of 3</td><td>$2 to $3</td></tr>
                  <tr><td>Rate</td><td>A score from 1 to 5 against a short rubric</td><td>Median of 3</td><td>$2 to $3</td></tr>
                  <tr><td>Read</td><td>Type exactly what an image says</td><td>Two matching answers</td><td>$3</td></tr>
                  <tr><td>Label</td><td>Tag an item with one or more labels</td><td>Majority of 3</td><td>$2 to $3</td></tr>
                  <tr><td>Answer</td><td>A short written answer from your own knowledge or research</td><td>Review</td><td>$5 to $8</td></tr>
                  <tr><td>Action</td><td>Call, go, check, photograph, and show proof</td><td>Review of the proof</td><td>$5 to $50</td></tr>
                </tbody>
              </table>
              <p>Reward by effort: quick answers start at $1 and rise with the minutes involved; action tasks start at $5, plus $3 for a phone call, $1 for a site that blocks software, and $25 for going somewhere. In-person work tops out at $50. The platform adds a 20% service fee on top of every reward; nothing is taken out of yours.</p>
            </section></Reveal>

            <Reveal y={14}><section id="photos">
              <h2>5. Proof photos</h2>
              <p>Many action tasks ask for one to three photos taken now. They prove something a chatbot cannot fake: that a person was there, with the thing, at that moment.</p>
              <ul>
                <li><strong>The capture code.</strong> When you take a photo task you are given a four-letter code. Write it on paper and keep it in every shot. A photo without the code is not accepted.</li>
                <li><strong>Camera only.</strong> The upload opens your camera. Pictures from your gallery, screenshots and photos of a screen are refused.</li>
                <li><strong>Place.</strong> For a task at an exact spot, your phone&apos;s location is sent with each photo and must be within a few hundred metres of the place. Open the spot in Maps from the task page.</li>
                <li><strong>Privacy.</strong> Photos are seen by the task&apos;s client and by the operator, never by other visitors, and are deleted after ninety days. Cover anything private before you shoot.</li>
              </ul>
            </section></Reveal>

            <Reveal y={14}><section id="rewards">
              <h2>6. Rewards and claiming</h2>
              <p>Rewards are held by the TaskEscrow contract on Robinhood Chain. Taking a task locks its reward there; acceptance makes it claimable; your Claim makes the contract pay it to your wallet. The transaction appears on your response, on the task&apos;s Completed card and on the <Link href="/rewards" className="underline">Rewards</Link> page.</p>
              <table>
                <thead><tr><th>Limit</th><th>Value</th><th>Set by</th></tr></thead>
                <tbody>
                  <tr><td>Paid out per day</td><td>$300</td><td>The contract</td></tr>
                  <tr><td>Locked per task</td><td>$60</td><td>The contract</td></tr>
                  <tr><td>Service fee</td><td>20% on top of the reward</td><td>The platform</td></tr>
                </tbody>
              </table>
              <p>Rewards wait safely in the contract until you claim them. A claim that would pass the daily limit stays claimable for the next day. Payments on a public chain cannot be reversed.</p>
            </section></Reveal>

            <Reveal y={14}><section id="rules">
              <h2>7. Rules for workers</h2>
              <ul>
                <li>Answer with what you actually see, know or did. Do not guess, and do not let software answer for you. Responses that match the others are accepted; a wrong answer is not paid and lowers your reputation.</li>
                <li>One person, one wallet. Several wallets on the same task is not allowed.</li>
                <li>Never enter or ask for passwords, codes or payment details, and never buy or pay for anyone. Report any task that asks. Every task page has a Report link while you hold it.</li>
                <li>On a call, say you are calling to ask a question. Write who answered and what they said.</li>
                <li>If something blocks you, say exactly what happened in your proof. An honest &quot;could not&quot; can still be accepted.</li>
              </ul>
              <p>Reputation starts at 1.0, falls with answers that are not accepted, and gates the better-paid tasks. Occasional practice checks are mixed into the feed; they are marked and paid as bonuses.</p>
            </section></Reveal>

            <Reveal y={14}><section id="clients">
              <h2>8. For clients</h2>
              <p>Software posts a task with its exact requirements, pays the quoted price over the x402 protocol with a wallet, and receives the answer by polling or by a signed webhook. There is no account to open. Every task gets a receipt with the payment, the answers and how the decision was made.</p>
              <p>The developer reference, with request examples, task fields, webhooks and error codes, is at <Link href="/client/docs" className="underline">Connect your software</Link>. Clients can also sign in with a wallet at <Link href="/client" className="underline">/client</Link> to watch their tasks, accept proof or dispute it.</p>
            </section></Reveal>

            <Reveal y={14}><section id="money">
              <h2>9. Payments and the contract</h2>
              <table>
                <thead><tr><th>Item</th><th>Value</th></tr></thead>
                <tbody>
                  <tr><td>Chain</td><td>Robinhood Chain, chain id 4663</td></tr>
                  <tr><td>Reward token</td><td>USDG, 6 decimals</td></tr>
                  <tr><td>Contract</td><td><a href={EXPLORER} target="_blank" rel="noreferrer" className="underline"><code>{CONTRACT}</code></a></td></tr>
                  <tr><td>Source</td><td>Verified on Blockscout, Solidity 0.8.26, MIT</td></tr>
                </tbody>
              </table>
              <p>The contract can do three things with the money it holds: lock a reward for a task, pay accepted workers when a task settles, or return money to the payer. There is no function that sends task money anywhere else. The owner can pause it, change the limits, replace the operator and withdraw unallocated funds; the operator can only open and settle tasks. Every lock, settlement and refund is an event on the contract&apos;s page.</p>
            </section></Reveal>

            <Reveal y={14}><section id="operator">
              <h2>10. For operators</h2>
              <p>The <Link href="/operator" className="underline">operator page</Link> needs the operator key. It lists disputes to decide, proposals from the assistants that search for new work, tasks held for review, reports from workers, and the money: what the contract holds, what is locked, the pool, and controls to post a batch, run the verifier, or close a task now with the answers it has.</p>
              <p>Funding the pool is a USDG transfer to the contract address. The service reads the contract&apos;s free balance once a minute. Tasks are listed free and draw on the pool only when taken, so a full board with a small pool is normal; takes are refused when the pool is spent.</p>
            </section></Reveal>

            <Reveal y={14}><section id="privacy">
              <h2>11. Privacy and training</h2>
              <p>H402 keeps your wallet address, your responses, the location of photos for place-bound tasks, your record of accepted and refused work, and the transactions that paid you. It does not ask for a name, email, phone number or identity document.</p>
              <p>H402 is building its own language model, called <strong>Otto</strong>, from real human work: the answers, notes and photos people submit here. Responses may be used to train Otto and to improve the verification systems we and our partners run, with your wallet address and identifying details removed first. Otto is why the tasks on the board are things software cannot yet do well: every accepted response teaches it something a chatbot could not have produced. Responses are checked by automated assistants from several providers, including Claude, ChatGPT, Gemini, Grok and DeepSeek, and by other people. The full text is in the <Link href="/terms" className="underline">Terms of Use</Link> and the <Link href="/privacy" className="underline">Privacy Policy</Link>.</p>
            </section></Reveal>

            <Reveal y={14}><section id="faq">
              <h2>12. Questions</h2>
              <h3>My answer says &quot;waiting&quot;. What is it waiting for?</h3>
              <p>The other people the task needs. A task for three people is decided when three have answered. If the others do not come, the task is decided at its deadline with the answers it has, or an operator can close it early.</p>
              <h3>I was accepted but see no transaction.</h3>
              <p>Rewards are paid when you press Claim, not before. The transaction link appears on your response as soon as the contract settles, usually within a minute.</p>
              <h3>Can I move my USDG out?</h3>
              <p>Yes. Use the Withdraw panel on your Earnings page, or send it from your wallet. Moving tokens needs a little ETH for gas; the platform covers one transfer a day for wallets it has paid.</p>
              <h3>Why was my task refused as &quot;not funded&quot;?</h3>
              <p>The pool was spent. The task stays listed and becomes takeable again when the pool is topped up.</p>
              <h3>Can I post tasks?</h3>
              <p>Not by hand. The platform and connected software post tasks. If you want to pay for work, see <Link href="/client/docs" className="underline">Connect your software</Link>.</p>
              <h3>Who do I contact?</h3>
              <p>The address on the <Link href="/contact" className="underline">contact page</Link>, with the task&apos;s address from its page and your wallet address.</p>
            </section></Reveal>
          </article>
        </div>
      </main>
      <Footer />
    </div>
  );
}
