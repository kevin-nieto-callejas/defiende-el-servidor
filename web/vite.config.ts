import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const nm = (ruta: string) => fileURLToPath(new URL(`./node_modules/three/${ruta}`, import.meta.url));

// El visor vive en src/rally/static (lo usa también `rally web`): aquí no se duplica.
// Como está fuera de web/, three se resuelve a mano desde web/node_modules.
export default defineConfig({
  resolve: {
    alias: [
      { find: /^three$/, replacement: nm("build/three.module.js") },
      { find: /^three\/addons\/(.*)$/, replacement: `${nm("examples/jsm")}/$1` },
    ],
  },
  build: { target: "esnext", chunkSizeWarningLimit: 1500 },
  server: {
    fs: { allow: [".."] },
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
