import "../../src/rally/static/style.css";
import "./catalogo.css";
import { montarCatalogo } from "./catalogo";
import { API_BASE } from "./config";
import { activarReplay, mostrarAviso } from "./replay";

(globalThis as { RALLY_API?: string }).RALLY_API = API_BASE;
const produccion = import.meta.env.PROD;

/**
 * En producción se pregunta a la API si está viva: la función de Vercel en el mismo dominio
 * (`/api`) o la URL de VITE_API_BASE_URL. Si no responde, la web entra en replay y dice por qué.
 * La primera consulta puede tardar unos segundos: la función arranca en frío.
 */
async function consultarApi(): Promise<string | null> {
  try {
    const r = await fetch(`${API_BASE}/api/salud`, { signal: AbortSignal.timeout(25000), cache: "no-store" });
    if (!r.ok) return `respondió ${r.status}`;
    const s = await r.json();
    return s.estado === "ok" ? null : `estado ${s.estado}`;
  } catch (e) {
    return (e as Error).name === "TimeoutError" ? "no respondió a tiempo" : "no está disponible";
  }
}

const motivoReplay = produccion ? await consultarApi() : null;
const replay = motivoReplay !== null;
if (replay) activarReplay();

// El visor es JavaScript compartido con `rally web`
await import("../../src/rally/static/app.js");
montarCatalogo();
if (replay) mostrarAviso(motivoReplay);
if (innerWidth <= 680) document.body.classList.add("plegado");  // en celular primero se ve la pista
if (produccion) document.getElementById("btn-vivo")?.remove();  // el entrenamiento no corre en la nube
