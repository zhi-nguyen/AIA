import type { Metadata } from "next";
import dynamic from "next/dynamic";
import "./globals.css";

const TauriSidecarInitializer = dynamic(
  () => import("@/components/TauriSidecarInitializer"),
  { ssr: false } // Vô hiệu hoá server-rendering vì chức năng này chỉ chạy trên Desktop UI client-side
);

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
      <body>
        <TauriSidecarInitializer />
        {children}
      </body>
    </html>
  );
}
