/** Variables públicas de la web (ver .env.example). */
export const API_BASE: string = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
export const COMMIT_WEB: string = import.meta.env.VITE_COMMIT || "local";
export const MLFLOW_URL: string =
  import.meta.env.VITE_MLFLOW_URL || "https://dagshub.com/kevin-nieto-callejas/autonomous-rally/experiments";
