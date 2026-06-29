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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function waitForBackend(baseUrl, attempts = 120) {
  /** Wait until the local backend accepts requests after Tauri starts it. */
  let lastError = null;
  for (let index = 0; index < attempts; index += 1) {
    try {
      const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });
      if (response.ok) {
        return true;
      }
      lastError = new Error(await response.text());
    } catch (error) {
      lastError = error;
    }
    await sleep(250);
  }
  throw lastError || new Error("Backend did not become ready");
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
