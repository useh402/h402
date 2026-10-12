import type { Metadata, Viewport } from "next";
import { Inter, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Announcement } from "@/components/announcement";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const serif = Source_Serif_4({ variable: "--font-serif", subsets: ["latin"], weight: ["200", "300", "400", "600"], style: ["normal", "italic"], display: "swap" });

export const metadata: Metadata = {
  title: "H402 — Real people, paid per task",
  description: "Clients post small tasks. Real people do them in minutes and are paid the moment the work is accepted. Paid in USDG on Robinhood Chain.",
  openGraph: { title: "H402 — Real people, paid per task", description: "Post a task, get a human answer in minutes, pay only when it is accepted.", type: "website" },
};

export const viewport: Viewport = { themeColor: "#080808" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${serif.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Providers>
          <Announcement />
          {children}
        </Providers>
      </body>
    </html>
  );
}
