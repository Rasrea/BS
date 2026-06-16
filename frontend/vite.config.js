import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { copyFileSync, mkdirSync, existsSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));

function copyWorkers() {
  const workers = [
    {
      src: "node_modules/@mlightcad/cad-simple-viewer/dist/mtext-renderer-worker.js",
      dest: "workers/mtext-renderer-worker.js",
    },
    {
      src: "node_modules/@mlightcad/cad-simple-viewer/dist/libredwg-parser-worker.js",
      dest: "workers/libredwg-parser-worker.js",
    },
    {
      src: "node_modules/@mlightcad/data-model/dist/dxf-parser-worker.js",
      dest: "workers/dxf-parser-worker.js",
    },
  ];

  return {
    name: "copy-workers",
    configureServer() {
      const publicDir = resolve(__dirname, "public");
      for (const w of workers) {
        const src = resolve(__dirname, w.src);
        const dest = resolve(publicDir, w.dest);
        if (existsSync(src)) {
          mkdirSync(dirname(dest), { recursive: true });
          copyFileSync(src, dest);
        }
      }
    },
    writeBundle() {
      const outDir = resolve(__dirname, "dist");
      for (const w of workers) {
        const src = resolve(__dirname, w.src);
        const dest = resolve(outDir, w.dest);
        if (existsSync(src)) {
          mkdirSync(dirname(dest), { recursive: true });
          copyFileSync(src, dest);
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [vue(), copyWorkers()],
  server: {
    port: 3001,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8100',
        changeOrigin: true,
      }
    }
  },
  optimizeDeps: {
    include: [
      "@mlightcad/cad-simple-viewer",
      "@mlightcad/data-model",
      "three",
      "lodash-es",
    ],
  },
  build: {
    modulePreload: false,
    minify: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
      },
    },
  },
})
