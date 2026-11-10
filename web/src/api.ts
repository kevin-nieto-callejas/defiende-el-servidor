import { API_BASE } from "./config";

export interface Resultado { vueltas_pct: number; tiempo_mediano_s: number | null }

export interface Version {
  nombre: string;
  tipo: "ppo" | "qlearning";
  etiqueta_git: string;
  level_id: string | null;
  decision: string | null;
  hipotesis: string | null;
  environment_version: string;
  git_commit: string;
  model_sha256: string;
  ejecutable: boolean;
  resultados: { seco?: Resultado; mojado?: Resultado } | null;
}

export interface Catalogo { recomendado: { modelo: string | null; motivo?: string }; modelos: Version[] }

export interface Salud {
  estado: string;
  ambiente: string;
  commit: string;
  episodios: number;
  errores: number;
  latencia_paso_ms: number | null;
  recomendado: { modelo: string | null };
  commit_paquete?: string | null;
  instancia_desde?: string;
}

export interface Evaluacion {
  vueltas_pct: number;
  tiempo_mediano_s: number | null;
  fallos_por_causa: Record<string, number>;
  ambiente_del_modelo: string | null;
  ambiente_servido: string;
  adaptador: boolean;
  motor: string;
  commit_servido: string;
  segundos: number;
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${ruta}`, init);
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.detail ?? `Error ${r.status}`);
  }
  return r.json();
}

export interface Monitoreo extends Salud {
  por_modelo: Record<string, number>;
  fallos: Record<string, number>;
}

export const monitoreo = () => pedir<Monitoreo>("/api/monitoreo");
export const catalogo = () => pedir<Catalogo>("/api/modelos");
export const salud = () => pedir<Salud>("/api/salud");
export const evaluar = (modelo: string, condiciones: Record<string, number>, pista = "monaco", episodios = 10) =>
  pedir<Evaluacion>("/api/evaluar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modelo, episodios, pista, ...condiciones }),
  });
