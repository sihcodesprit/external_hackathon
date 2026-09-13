import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: ".",
  base: "/",
  plugins: [react()],
  build: {
    outDir: "dist",
    sourcemap: false,
    cssCodeSplit: true,
    minify: "esbuild",
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
        manualChunks: {
          vendor: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});