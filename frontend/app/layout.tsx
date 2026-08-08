import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Insurance Decision Intelligence Platform",
  description: "Enterprise insurance intelligence platform with customer, agent, campaign, lapse risk, and AI intelligence workspaces"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
