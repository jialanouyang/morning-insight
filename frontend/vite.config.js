import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地开发 / 预览时，把 /api 请求代理到后端；生产由 nginx 反代（见 nginx.conf）
// 注意：默认用 127.0.0.1 而非 localhost —— Windows 下 localhost 可能优先解析到 ::1，
// 而后端只监听 IPv4，会出现「upstream connect failed」。
const proxy = {
  "/api": {
    target: process.env.API_TARGET || "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { outDir: "dist", sourcemap: false },
});
