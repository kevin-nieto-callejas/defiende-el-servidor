/**
 * Modo replay: sin API pública, /api/* se responde con los archivos de public/datos/.
 * Todo se marca como replay; lo que necesita simular responde error, nunca un dato inventado.
 */
const SIN_API = "Esta función necesita la API de simulación, que aún no está publicada.";

function destino(url: URL): string | null {
  if (url.pathname === "/api/pista") return "/datos/pista.json";
  if (url.pathname === "/api/modelos") return "/datos/modelos.json";
  if (url.pathname === "/api/salud") return "/datos/salud.json";
  if (url.pathname === "/api/episodio") {
    const p = url.searchParams, num = (k: string) => parseFloat(p.get(k) ?? "");
    const clima = num("mu") === 0.9 ? "seco" : num("mu") === 0.5 ? "lluvia" : null;
    // Solo hay grabada la condición base: otra combinación no se aproxima con una vuelta que no le corresponde
    if (!clima || num("ancho") !== 8 || num("a_max") !== 4 || num("r_max") !== 20 || num("semilla") !== 0) return null;
    return `/datos/replays/${encodeURIComponent(p.get("piloto") ?? "")}-${clima}.json`;
  }
  return null;
}

export function activarReplay() {
  const original = globalThis.fetch.bind(globalThis);
  globalThis.fetch = async (entrada, init) => {
    const url = new URL(entrada instanceof Request ? entrada.url : String(entrada), location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/")) return original(entrada, init);
    const ruta = destino(url);
    const r = ruta ? await original(ruta) : null;
    if (r?.ok) return r;
    return new Response(JSON.stringify({ detail: SIN_API }), { status: 503 });
  };
}

/** El aviso va en la nota del panel: en replay "cada corrida es una simulación nueva" no es cierto. */
export function mostrarAviso() {
  const nota = document.querySelector(".nota-normal");
  if (!nota) return;
  nota.textContent = "Modo replay: vueltas grabadas con semilla 0 y parámetros base. Cambiar otro valor necesita la API.";
  nota.classList.replace("nota-normal", "nota-replay");
  nota.parentElement?.prepend(nota);  // arriba: en pantallas bajas el final del panel queda bajo el scroll
}
