import "../../src/rally/static/style.css";
import "./catalogo.css";
import { montarCatalogo } from "./catalogo";
import { API_BASE } from "./config";
import { activarReplay, mostrarAviso } from "./replay";

(globalThis as { RALLY_API?: string }).RALLY_API = API_BASE;
const produccion = import.meta.env.PROD;
const replay = produccion && !API_BASE;
if (replay) activarReplay();

// El visor es JavaScript compartido con `rally web`
await import("../../src/rally/static/app.js");
montarCatalogo();
if (replay) mostrarAviso();
if (produccion) document.getElementById("btn-vivo")?.remove();  // el entrenamiento no corre en la nube
