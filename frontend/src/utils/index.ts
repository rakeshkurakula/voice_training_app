import { ConnectionStatus } from '../types';

export const apiBase = "http://localhost:8000";

export function clsx(...parts: Array<string | undefined | false>) {
  return parts.filter(Boolean).join(" ");
}

export function scoreColor(score: number) {
  if (score >= 85) return "text-emerald-600"; // 🟢
  if (score >= 70) return "text-amber-600"; // 🟡
  return "text-rose-600"; // 🔴
}

export function badgeColorByScore(score: number) {
  if (score >= 85) return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (score >= 70) return "bg-amber-50 text-amber-800 border-amber-200";
  return "bg-rose-50 text-rose-700 border-rose-200";
}

export function statusDotColor(status: ConnectionStatus) {
  switch (status) {
    case "connecting":
      return "bg-amber-400";
    case "connected":
      return "bg-emerald-500";
    case "disconnected":
      return "bg-slate-400";
    case "error":
      return "bg-rose-500";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
    const res = await fetch(`${apiBase}${path}`);
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
}

export async function apiPost<T>(path: string, body: any): Promise<T> {
    const res = await fetch(`${apiBase}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${path} → ${res.status}`);
    return res.json();
}

export function arrayBufferToBase64(buffer: ArrayBuffer) {
  let binary = "";
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
