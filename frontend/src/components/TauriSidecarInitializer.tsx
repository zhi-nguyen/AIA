"use client";

import { useEffect } from "react";

export default function TauriSidecarInitializer() {
  useEffect(() => {
    let sidecarInstance: any = null;

    const startSidecar = async () => {
      try {
        console.log("Đang khởi động AIA_Agent Backend...");
        const { Command } = await import("@tauri-apps/plugin-shell");
        const command = Command.sidecar("bin/AIA_Agent");
        
        command.on("close", (data) => {
          console.log(`Backend AIA_Agent đã đóng với mã code: ${data.code} và signal: ${data.signal}`);
        });

        command.on("error", (error) => {
          console.error(`Lỗi AIA_Agent lệnh shell: "${error}"`);
        });

        sidecarInstance = await command.spawn();
        console.log("Backend AIA_Agent Sidecar PID:", sidecarInstance.pid);
      } catch (error) {
        // Có thể catch mượt mà nếu UI đang tự chạy web browser không nằm trong tauri desktop env
        console.warn("Không khởi chạy được Sidecar. Nếu đây là trình duyệt web, vui lòng bỏ qua dòng này.", error);
      }
    };

    startSidecar();

    return () => {
      // Cleanup: khi giao diện tắt, hãy kill sidecar để giải phóng port
      if (sidecarInstance) {
        sidecarInstance.kill();
      }
    };
  }, []);

  return null;
}
