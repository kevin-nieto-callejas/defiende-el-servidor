import * as api from "./api";
import type { Evaluacion, Version } from "./api";
import { COMMIT_WEB, MLFLOW_URL } from "./config";

const pct = (v?: { vueltas_pct: number }) => (v ? `${v.vueltas_pct}%` : "—");
const corto = (s: string) => s.slice(0, 8);

function esc(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

/** Lee los deslizadores del visor: la evaluación corre con lo que el docente ve en pantalla. */
function condiciones(): Record<string, number> {
  const c: Record<string, number> = {};
  for (const k of ["ancho", "mu", "a_max", "r_max"]) {
    const i = document.getElementById(`p-${k}`) as HTMLInputElement | null;
    if (i) c[k] = parseFloat(i.value);
  }
  return c;
}

/** Pista que se ve en el visor (?pista=): la evaluación corre en esa misma pista. */
function pistaActual(): string {
  return new URLSearchParams(location.search).get("pista") ?? "monaco";
}

function fila(v: Version, recomendado: string | null): string {
  const r = v.resultados ?? {};
  const acciones = v.ejecutable
    ? `<button data-cargar="${esc(v.nombre)}">Cargar</button><button data-evaluar="${esc(v.nombre)}">Evaluar</button>
       <input type="checkbox" data-comparar="${esc(v.nombre)}" aria-label="Comparar ${esc(v.nombre)}">`
    : `<span title="Discretización antigua: se conserva como evidencia">solo evidencia</span>`;
  return `<tr class="${v.nombre === recomendado ? "recomendada" : ""}" title="${esc(v.hipotesis ?? "")}">
    <td><b>${esc(v.etiqueta_git)}</b><br><small>${esc(v.tipo)}</small></td>
    <td>${esc(v.level_id ?? "—")}</td><td>${esc(v.decision ?? "—")}</td>
    <td>${esc(v.environment_version)}</td>
    <td class="mono">${corto(v.git_commit)}<br><small>sha ${corto(v.model_sha256)}</small></td>
    <td class="mono">${pct(r.seco)}</td><td class="mono">${pct(r.mojado)}</td>
    <td class="acciones-cat">${acciones}</td></tr>`;
}

function resumen(nombre: string, e: Evaluacion): string {
  const fallos = Object.entries(e.fallos_por_causa).map(([k, n]) => `${k}: ${n}`).join(" · ");
  return `<tr><td><b>${esc(nombre)}</b></td><td class="mono">${e.vueltas_pct}%</td>
    <td class="mono">${e.tiempo_mediano_s ?? "—"} s</td><td>${esc(fallos)}</td>
    <td>${esc(e.ambiente_del_modelo ?? e.ambiente_servido)}${e.adaptador ? " (adaptador)" : ""} · ${esc(e.motor)}</td></tr>`;
}

async function correr(nombres: string[], salida: HTMLElement) {
  const c = condiciones(), pista = pistaActual();
  salida.textContent = `Evaluando ${nombres.join(", ")} en ${pista} con 10 semillas…`;
  try {
    const res = await Promise.all(nombres.map((n) => api.evaluar(n, c, pista)));
    salida.innerHTML = `<table><thead><tr><th>Versión</th><th>Vueltas</th><th>Tiempo</th><th>Fin</th><th>Ambiente</th></tr></thead>
      <tbody>${res.map((e, i) => resumen(nombres[i], e)).join("")}</tbody></table>
      <p>Pista: ${esc(pista)} · condición: ${esc(JSON.stringify(c))} · modelo congelado · API en ${corto(res[0].commit_servido)}</p>`;
  } catch (e) {
    salida.textContent = `Error del servicio: ${(e as Error).message}`;
  }
}

function cargarEnVisor(nombre: string, panel: HTMLElement) {
  const sel = document.getElementById("sel-piloto") as HTMLSelectElement;
  sel.value = nombre;
  document.getElementById("btn-correr")?.click();
  panel.classList.add("oculto");
}

/** Monitoreo mínimo de la guía: éxito por modelo, causas de fallo, latencia y versión servida. */
async function pintarMonitoreo(panel: HTMLElement) {
  const caja = panel.querySelector<HTMLElement>("#cat-monitoreo")!;
  try {
    const m = await api.monitoreo();
    const fin = (d: Record<string, number>) => Object.entries(d).map(([k, n]) => `${esc(k)}: ${n}`).join(" · ") || "sin datos";
    const desde = m.instancia_desde ? ` (instancia activa desde ${esc(m.instancia_desde)})` : "";
    caja.innerHTML = `<h3>Monitoreo de la API${desde}</h3>
      <p>Finales de episodio: ${fin(m.fallos)}</p><p>Episodios por versión: ${fin(m.por_modelo)}</p>
      <p>Latencia ${m.latencia_paso_ms ?? "—"} ms por paso · ${m.errores} errores · sirve ${esc(m.recomendado.modelo ?? "sin promover")}</p>`;
  } catch {
    caja.textContent = "El monitoreo en vivo necesita la API.";
  }
}

async function abrir(panel: HTMLElement) {
  panel.classList.remove("oculto");
  const cuerpo = panel.querySelector<HTMLElement>("#cat-cuerpo")!;
  const estado = panel.querySelector<HTMLElement>("#cat-estado")!;
  cuerpo.textContent = "Consultando el catálogo…";
  pintarMonitoreo(panel);
  try {
    const [cat, s] = await Promise.all([api.catalogo(), api.salud()]);
    estado.innerHTML = `API ${esc(s.estado)} · ambiente ${esc(s.ambiente)} · commit ${corto(s.commit)} · web ${esc(corto(COMMIT_WEB))}
      · recomendado <b>${esc(s.recomendado.modelo ?? "sin promover")}</b>
      · ${s.episodios} episodios, ${s.errores} errores, ${s.latencia_paso_ms ?? "—"} ms por paso
      · <a href="${MLFLOW_URL}" target="_blank" rel="noopener">Abrir MLflow</a>`;
    cuerpo.innerHTML = `<table><thead><tr><th>Versión</th><th>Nivel</th><th>Decisión</th><th>Ambiente</th><th>Commit</th>
      <th>Seco</th><th>Lluvia</th><th></th></tr></thead>
      <tbody>${cat.modelos.map((v) => fila(v, cat.recomendado.modelo)).join("")}</tbody></table>`;
  } catch (e) {
    cuerpo.textContent = `Error del servicio: ${(e as Error).message}`;
  }
}

/** Agrega el botón y el panel de catálogo: consultar, cargar, evaluar y comparar versiones. */
export function montarCatalogo() {
  const panel = document.createElement("section");
  panel.id = "catalogo";
  panel.className = "oculto";
  panel.innerHTML = `<header><h2>Catálogo de modelos</h2><button id="cat-cerrar" aria-label="Cerrar">✕</button></header>
    <p id="cat-estado"></p><div id="cat-cuerpo"></div>
    <div class="cat-pie"><button id="cat-comparar">Comparar marcadas</button></div><div id="cat-salida" aria-live="polite"></div>
    <div id="cat-monitoreo"></div>`;
  document.body.append(panel);
  addEventListener("keydown", (ev) => { if (ev.key === "Escape") panel.classList.add("oculto"); });

  const boton = document.createElement("button");
  boton.textContent = "Catálogo";
  boton.onclick = () => abrir(panel);
  document.getElementById("acciones")?.prepend(boton);

  const salida = panel.querySelector<HTMLElement>("#cat-salida")!;
  panel.addEventListener("click", (ev) => {
    const b = ev.target as HTMLElement;
    if (b.id === "cat-cerrar") panel.classList.add("oculto");
    if (b.dataset.cargar) cargarEnVisor(b.dataset.cargar, panel);
    if (b.dataset.evaluar) correr([b.dataset.evaluar], salida);
    if (b.id === "cat-comparar") {
      const marcadas = [...panel.querySelectorAll<HTMLInputElement>("[data-comparar]:checked")].map((c) => c.dataset.comparar!);
      if (marcadas.length >= 2) correr(marcadas.slice(0, 4), salida);
      else salida.textContent = "Marca al menos dos versiones.";
    }
  });
}
