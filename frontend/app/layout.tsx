import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Fieldwork — Internship workspace",
  description: "Discover relevant companies. Build thoughtful connections.",
  icons: { icon: "/favicon.svg" },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
