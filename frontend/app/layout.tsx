import type { Metadata } from "next";
import { AuthProvider } from "@/context/auth-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aegis · Ocena ryzyka kontrahenta",
  description: "Obszar roboczy do udokumentowanej oceny ryzyka kontrahentów",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pl">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
