"use client";

/** The assistant a task is for. Official marks, stored in /public/brands. */
export const REQUESTERS: Record<string, { label: string; file: string; glow: string }> = {
  claude: { label: "Claude", file: "claude-color", glow: "#d97757" },
  chatgpt: { label: "ChatGPT", file: "openai", glow: "#ffffff" },
  gemini: { label: "Gemini", file: "gemini-color", glow: "#4f8ff7" },
  grok: { label: "Grok", file: "grok", glow: "#ffffff" },
  deepseek: { label: "DeepSeek", file: "deepseek-color", glow: "#4d6bfe" },
};

export function requesterFor(key: string | null | undefined) {
  return (key && REQUESTERS[key]) || null;
}

export function RequesterMark({ requester, size = 56 }: { requester: string | null | undefined; size?: number }) {
  const r = requesterFor(requester);
  if (!r) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={`/brands/${r.file}.svg`} alt={r.label} width={size} height={size} style={{ width: size, height: size }} />;
}
