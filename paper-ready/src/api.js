import { invoke } from "@tauri-apps/api/core";

export const fallbackBackendUrl = "http://127.0.0.1:8765";

export async function resolveBackendUrl() {
  /** Resolve the backend URL from Tauri, falling back for web development. */
  try {
    return await invoke("backend_url");
  } catch {
    return fallbackBackendUrl;
  }
}

export async function apiRequest(baseUrl, path, options = {}) {
  /** Call the local backend and raise API failures as Error objects. */
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

