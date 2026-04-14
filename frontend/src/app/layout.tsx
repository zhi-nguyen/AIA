import type { Metadata } from "next";
import TauriSidecarInitializer from "@/components/TauriSidecarInitializer";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIA - Trợ Lý AI Cá Nhân",
  description: "Multi-Agent AI Personal Assistant - Email, News, and General Chat",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="antialiased">
        <TauriSidecarInitializer />
        {children}
      </body>
    </html>
  );
}
