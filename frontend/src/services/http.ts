export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`http://localhost:8000${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export async function postFile<T>(path: string, file: File | Blob, filename = 'audio.webm', field = 'file'): Promise<T> {
  const fd = new FormData();
  fd.append(field, file, filename);
  const res = await fetch(`http://localhost:8000${path}`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}
