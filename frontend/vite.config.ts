import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

const plugins = [react(), tailwindcss()];

export default defineConfig({
  plugins,
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
      "@shared": path.resolve(import.meta.dirname, "src", "shared"),
    },
  },
  // Project root is the frontend directory itself: index.html, public/ and
  // src/ all sit here, which is the layout Vite documents and every tool
  // expects. Previously the app was nested one level deeper in client/, so
  // root, aliases and outDir each needed their own override to compensate.
  root: import.meta.dirname,
  envDir: import.meta.dirname,
  publicDir: path.resolve(import.meta.dirname, "public"),
  // Relative asset URLs. The app uses hash routing, so a static host needs no
  // rewrite rules — and with "./" the build also works when uploaded into a
  // subdirectory (e.g. Hostinger's public_html/app/) instead of only at the
  // domain root, where absolute "/assets/..." paths would 404.
  base: "./",
  build: {
    outDir: path.resolve(import.meta.dirname, "dist"),
    emptyOutDir: true,
  },
  server: {
    port: 3000,
    strictPort: false, // Will find next available port if 3000 is busy
    host: true,
    allowedHosts: ["localhost", "127.0.0.1", ".devtunnels.ms", ".ngrok-free.app", ".trycloudflare.com", ".loca.lt"],
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
  },
});
