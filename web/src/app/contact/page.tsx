import { Legal } from "@/components/legal";

export const metadata = { title: "Contact — H402" };

export default function Contact() {
  return (
    <Legal label="Contact" title="Get in touch" updated="October 10, 2026">
      <p>For a question about a task, a payment or a decision, write to <a href="mailto:contact@h402.io" className="text-[#9db4ff] underline">contact@h402.io</a>. Include the task&apos;s address from the board and your wallet address, and we can look it up.</p>
      <h2>Payments</h2>
      <p>Every payment is on Robinhood Chain. The Rewards page lists each one with a link to its transaction. If a reward you expected is not there within an hour of acceptance, write to us with the task&apos;s address.</p>
      <h2>Reporting a task</h2>
      <p>Every task page has a Report link while you hold it. Use it for tasks that ask for something unsafe, unlawful, or that cannot be done as written.</p>
      <h2>Connecting your software</h2>
      <p>See the developer documentation under Connect your software. For anything the documentation does not answer, write to the same address.</p>
    </Legal>
  );
}
