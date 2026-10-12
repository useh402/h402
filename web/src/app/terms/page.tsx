import { Legal } from "@/components/legal";

export const metadata = { title: "Terms of Use — H402" };

export default function Terms() {
  return (
    <Legal label="Terms" title="Terms of Use" updated="October 10, 2026">
      <p>H402 is a marketplace where tasks are done by people for a fixed reward paid in stablecoins. By connecting a wallet or using the service you agree to these terms.</p>
      <h2>1. Who can take tasks</h2>
      <p>You must be at least 18 and able to do the task where it says. Tasks are for people in the United States. You take tasks as an independent person, not as an employee or contractor of H402.</p>
      <h2>2. Rewards and payment</h2>
      <p>Each task shows its reward before you take it. A reward is paid when the response is accepted: by agreement with other people for quick tasks, or by review for tasks with proof. Payment goes to the wallet you connected, in USDG on Robinhood Chain, from a contract on that chain. H402 charges the task&apos;s client a service fee on top of the reward; nothing is deducted from your reward.</p>
      <p>A response that is not accepted is not paid. Payments on a public chain cannot be reversed. Moving funds out of your wallet needs network gas, which you pay or which H402 may cover once a day for wallets it has paid.</p>
      <h2>3. Doing the work honestly</h2>
      <ul>
        <li>Answer with what you actually see, know or did. Do not guess, and do not use software to answer for you.</li>
        <li>Photos must be taken by you, at the time and place the task says, and show the capture code you are given.</li>
        <li>One person, one wallet. Running several wallets to answer the same task is not allowed.</li>
        <li>Do not submit content that is unlawful, infringing, or that exposes other people&apos;s private information.</li>
      </ul>
      <p>Responses that break these rules are not paid. Repeated breaches lower a wallet&apos;s reputation and can end its access.</p>
      <h2>4. Content you submit</h2>
      <p>You keep ownership of your responses and photos. You grant H402 and the task&apos;s client a licence to use them for the purpose of the task, to decide whether the response is accepted, and to keep records. Responses to decided tasks may be shown on the task page without your wallet address. Photos are shown only to the client and the operator, and are deleted after ninety days.</p>
      <h2>5. Training and automated review</h2>
      <p>H402 is building its own language model, named Otto. Responses, notes and photos you submit may be used to train Otto and to improve the verification systems operated by H402 and by its partners. Your wallet address and any identifying details are removed first. Responses are reviewed by automated assistants from several providers, including Claude, ChatGPT, Gemini, Grok and DeepSeek, and compared with other people&apos;s responses, before an operator decides anything the assistants cannot. If you do not want your responses used this way, do not submit them.</p>
      <h2>6. Disputes</h2>
      <p>If a response is marked wrong or unsure, an operator decides. You can contact us about a decision. Decisions about acceptance are final once made.</p>
      <h2>7. No warranty, limited liability</h2>
      <p>The service is provided as is. H402 is not liable for losses from chain failures, wallet issues, or tasks that are withdrawn or expire. Our total liability to you is limited to the rewards owed to you for accepted work.</p>
      <h2>8. Changes</h2>
      <p>We may change these terms. The date above shows the current version. Continued use after a change means you accept it.</p>
      <h2>9. Contact</h2>
      <p>Questions go to the address on the contact page.</p>
    </Legal>
  );
}
