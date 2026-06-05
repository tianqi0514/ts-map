const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export async function api<T>(path: string, options: RequestInit = {}): Promise<{ success: boolean; data: T; error: string | null }> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}
