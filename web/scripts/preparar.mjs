// Genera web/index.html desde el del visor: quita el importmap del CDN (Vite usa three de
// npm) y carga la entrada TypeScript. Así solo hay un HTML que mantener.
import { readFileSync, writeFileSync } from "node:fs";

const origen = new URL("../../src/rally/static/index.html", import.meta.url);
const html = readFileSync(origen, "utf8")
  .replace(/\s*<script type="importmap">[\s\S]*?<\/script>/, "")
  .replace(/\s*<link rel="stylesheet" href="style\.css">/, "")
  .replace('<script type="module" src="app.js"></script>', '<script type="module" src="/src/main.ts"></script>');
if (html.includes("importmap") || !html.includes("/src/main.ts")) throw new Error("index.html cambió: revisar preparar.mjs");
writeFileSync(new URL("../index.html", import.meta.url), html);
