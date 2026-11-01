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
    const clima = parseFloat(url.searchParams.get("mu") ?? "0.9") < 0.75 ? "lluvia" : "seco";
    return `/datos/replays/${encodeURIComponent(url.searchParams.get("piloto") ?? "")}-${clima}.json`;
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

export function mostrarAviso() {
  const aviso = document.createElement("p");
  aviso.id = "aviso-replay";
  aviso.textContent = "Modo replay: vueltas grabadas con semilla 0 y parámetros base. Los deslizadores y la evaluación en vivo necesitan la API.";
  document.body.append(aviso);
}
