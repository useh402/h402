import { Legal } from "@/components/legal";

export const metadata = { title: "Privacy Policy — H402" };

export default function Privacy() {
  return (
    <Legal label="Privacy" title="Privacy Policy" updated="October 10, 2026">
      <p>This page says what H402 keeps about you and why. We keep as little as the service needs.</p>
      <h2>What we keep</h2>
      <ul>
        <li><strong>Your wallet address.</strong> It is your account and the place rewards are paid. We never hold your keys.</li>
        <li><strong>Your responses.</strong> Every answer, note and photo you submit, with the time it was submitted and how long it took.</li>
        <li><strong>Photo location.</strong> For tasks that must be done at a place, the location your device reports when a photo is taken, used only to check the photo was taken there.</li>
        <li><strong>Your record.</strong> Tasks taken, accepted and not accepted, and a reputation figure derived from them.</li>
        <li><strong>Payments.</strong> The on-chain transactions that paid you. These are public on Robinhood Chain.</li>
      </ul>
      <p>We do not ask for your name, email, phone number or identity documents. Wallet connection is handled by Privy, which has its own privacy policy.</p>
      <h2>Who sees it</h2>
      <ul>
        <li><strong>The task&apos;s client</strong> sees your responses and photos for its task, without your wallet address.</li>
        <li><strong>Other visitors</strong> see responses to decided tasks. Accepted responses show the wallet address the reward is paid to, so the people on a task can see who is owed what; other responses show a short anonymous label. Photos and locations are never shown.</li>
        <li><strong>H402 operators</strong> see everything above when deciding disputes and reviewing work.</li>
        <li><strong>Review assistants.</strong> Responses and photos are sent to automated assistants from several providers (Claude, ChatGPT, Gemini, Grok and DeepSeek) to check them against the task. They are sent as data for that check.</li>
        <li><strong>Model training.</strong> Responses, notes and photos may be used to train Otto, the language model H402 is building, and to improve the verification systems we and our partners run, with your wallet address and identifying details removed first.</li>
      </ul>
      <h2>How long</h2>
      <p>Task content and responses are removed thirty days after a task is decided. Photos are deleted after ninety days at the latest. Payment records and your wallet&apos;s record are kept while you use the service.</p>
      <h2>Where it lives</h2>
      <p>Records are stored with hosting providers in the United States. Photos are stored with a separate hosting provider under the same rules.</p>
      <h2>Your choices</h2>
      <p>You can stop using the service at any time by disconnecting your wallet. To have your responses removed early, or to ask what we hold for your wallet, contact us using the address on the contact page and sign a message from that wallet so we know it is you.</p>
      <h2>Cookies and storage</h2>
      <p>The site keeps a sign-in token in your browser&apos;s storage so you stay signed in. There is no advertising and no tracking across other sites.</p>
    </Legal>
  );
}
