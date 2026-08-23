import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Amharic Document AI",
  description:
    "Turn a phone photo of an Ethiopian document into structured Markdown and JSON.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
