# VoiceCoach — Component Architecture & Best Practices

> Objective: make the dashboard **robust, testable, and scalable**. Below is a component‑wise blueprint with patterns, contracts, and checklists you can apply incrementally.

---

## 1) Component Map (responsibilities, inputs/outputs)

**AppShell**

* *Owns*: layout grid, theme, error boundary, feature flags, providers (Query/State/Telemetry).
* *Children*: `TopBar`, `StatsStrip`, `ChartsArea`, `SessionControls`, `DrillsPanel`, `MetricsPanel`, `TrainingPlan`.

**TopBar**

* *Props*: `user`, `status` (api/mic), `streak`.
* *Notes*: avoid business logic; renders presence/health badges only.

**StatsStrip**

* *Props*: `{ level, latestScore, streakDays, sessions }`.
* *Pattern*: pure presentational cards; no hooks.

**ChartsArea**

* *Props*: `{ accuracySeries, werSeries }`.
* *Notes*: accept already shaped series; charting components should be **pure**.

**SessionControls** (critical)
̀
* *Props*: `recorder` adapter, `guided: boolean`, callbacks: `onStart`, `onStop`, `onReset`, `onUpload(file)`.
* *Renders*: buttons, status hints, timer, audio preview.
* *Does not*: touch `getUserMedia` directly; uses `recorder` interface.

**RecorderPanel (headless)**

* *Implements*: `Recorder` interface using a **hook + adapter** (see §3). Emits `{ status, error, blob, duration }`.
* *UI‑less*: consumed by `SessionControls`.

**DrillsPanel**

* *Props*: `drills: Drill[]`, `activeId`, `onChange(id)`.
* *Optional*: `onGenerateLLM(params)` to insert new drills.

**MetricsPanel**

* *Props*: `{ transcript, metrics }` and `targets`. Emits `onTranscriptChange`.
* *Headless calc*: `computeMetrics` resides in `/lib/metrics.ts` and is unit‑tested.

**TrainingPlan**

* *Props*: `steps: Step[]`, `onCheck(stepId, done)`; no network calls.

**LlmPanel (optional)**

* *Props*: `onInsert(drills[])`, `onCritique({transcript, metrics})`.
* *Notes*: all API calls via `/services/llm.ts`.

---

## 2) State Model & Data Flow

* **Server state** (ASR, LLM, history): use **TanStack Query** (retry, cache, dedupe, suspense‑ready).
* **Client state** (UI toggles, active drill): use **Zustand** or `useReducer` in Context for minimal shared state.
* **One‑way data flow**: `RecorderPanel → SessionControls → transcript → MetricsPanel → (Critique)`.
* **Events**: small typed event bus for analytics (see §7).

```ts
// /types/recorder.ts
export type RecorderStatus = 'idle'|'requesting'|'recording'|'denied'|'unsupported'|'error'|'uploading';
export interface Recorder {
  status: RecorderStatus; duration: number; audioUrl?: string; error?: string;
  start(): Promise<void>; stop(): void; reset(): void; setFromFile(file: File): void;
}
```

---

## 3) Robust Recording (adapter pattern)

**Why**: isolate `getUserMedia` + browser quirks from UI.

* `useRecorderBrowser()` implements `Recorder` using MediaRecorder.
* `useRecorderMock()` returns the same interface for tests/sandboxes.
* Select adapter via feature detection + env flag.

```ts
// /adapters/recorder/browser.ts
export function useRecorderBrowser(): Recorder { /* guards: secureContext, Permissions API, cleanup, user-gesture */ }
```

**Guards**

1. **Secure context**: `isSecureContext || hostname in [localhost, 127.0.0.1]`.
2. **Feature check**: `navigator.mediaDevices?.getUserMedia`.
3. **User gesture**: call `getUserMedia` **only** inside click handler.
4. **Permissions API** (best‑effort): `navigator.permissions?.query({name:'microphone' as any})` → pre‑message.
5. **Cleanup**: stop all tracks on `stop` and `unmount`.
6. **Timeout**: treat stuck `requesting` (>10s) as error with guidance.
7. **Fallback**: `Upload audio` pathway always present.

---

## 4) Error Boundaries & Status UX

* Global **ErrorBoundary** around `AppShell` (use `react-error-boundary`).
* Local boundary around `ChartsArea` (chart libs can throw on size 0).
* Status taxonomy: `idle/requesting/recording/denied/unsupported/error/uploading` with distinct UI copy.
* Never `alert()` in production; use toasts/inline banners.

```tsx
<ErrorBoundary FallbackComponent={AppCrashed} onReset={resetApp}>
  <AppProviders>
    <AppShell />
  </AppProviders>
</ErrorBoundary>
```

---

## 5) Accessibility & Keyboard

* Buttons: `aria-pressed` for Record toggle; `aria-live="polite"` for timers.
* Provide **keyboard shortcuts**: `R` record/stop, `U` upload, `T` focus transcript.
* Focus management: send focus to Stop when recording starts; return to Record after stop.
* Color contrast ≥ 4.5:1; don’t rely on color alone for state.

---

## 6) Performance

* Memoize heavy charts; feed **preformatted series**.
* `React.Suspense` integration ready (for future streaming ASR/LLM).
* Avoid re‑renders: child components **pure**; use `memo` where props stable.
* Use **Web Worker** for offline metrics (WER, pitch) if heavy.
* Lazy‑load LLM panel and chart library chunks.

---

## 7) Observability (logs + analytics)

* Wrap `console` into a structured logger with levels; disable in prod.
* Telemetry events (minimal PII):

  * `record.started`, `record.stopped` {duration}
  * `asr.request`, `asr.success|failure` {ms}
  * `llm.generate`, `llm.critique`
* Add `window.performance.mark/measure` around ASR & LLM calls.

---

## 8) Security & Privacy

* Run on `localhost` during dev; HTTPS for staging/prod.
* Don’t store raw audio by default; keep object URLs ephemeral; revoke on unmount.
* Redact PII in transcripts before sending to LLM; allow user opt‑out.
* Rate limit backend; validate MIME/type + size on upload (10–30 MB).

---

## 9) API/Service Layer

* All fetch logic in `/services/*.ts` using a tiny wrapper (handles base URL, retries, zod validation).
* Contracts live in `/types` and are shared with the backend (openapi or manual `zod` schemas).

```ts
// /services/http.ts
export async function postJson<T>(url: string, body: unknown): Promise<T> { /* fetch wrapper with zod parse */ }
```

---

## 10) Testing Matrix

* **Unit**: `computeMetrics`, `recorder` adapter (mock MediaRecorder), helpers.
* **Component**: `SessionControls` (start/stop/upload flows), `MetricsPanel` rendering.
* **Integration (Playwright)**: happy path (record 5s), upload path, denied flow copy visible.
* **Contract**: mock server for `/asr` & `/llm/*` returns required shapes.

*Edge cases*: mic denied, no device, user stops instantly (<1s), 10‑minute file, empty transcript, non‑English text.

---

## 11) Styling & Layout Discipline

* Grid parents: `items-stretch min-w-0`; cards: `h-full flex flex-col`.
* Chart containers: `flex-1 min-h-[16rem]`.
* Tabs: `overflow-x-auto` + hidden scrollbar; labels `whitespace-nowrap`.
* Avoid layout shift: reserve height for async panels.

---

## 12) Example: Recorder Adapter Skeleton (TypeScript)

```ts
// /adapters/recorder/browser.ts
import { useEffect, useRef, useState } from 'react';
export function useRecorderBrowser(): Recorder {
  const [status, setStatus] = useState<RecorderStatus>('idle');
  const [duration, setDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string>();
  const [error, setError] = useState<string>();
  const mediaRef = useRef<MediaRecorder|null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number>();

  useEffect(()=>()=>{ mediaRef.current?.stream.getTracks().forEach(t=>t.stop()); if (timer.current) clearInterval(timer.current); },[]);

  async function start(){
    if (!('mediaDevices' in navigator) || !navigator.mediaDevices.getUserMedia){ setStatus('unsupported'); setError('Mic not supported'); return; }
    setError(undefined); setStatus('requesting');
    try{
      const stream = await navigator.mediaDevices.getUserMedia({audio:true});
      const mr = new MediaRecorder(stream); mediaRef.current = mr; chunks.current = []; setDuration(0);
      mr.ondataavailable = (e)=>{ if(e.data.size>0) chunks.current.push(e.data); };
      mr.onstop = ()=>{ const blob=new Blob(chunks.current,{type:'audio/webm'}); setAudioUrl(URL.createObjectURL(blob)); stream.getTracks().forEach(t=>t.stop()); if (timer.current) clearInterval(timer.current); };
      mr.start(100); setStatus('recording'); timer.current = window.setInterval(()=> setDuration(d=>d+1),1000);
    }catch(e:any){ setStatus(e?.name==='NotAllowedError'?'denied':'error'); setError(e?.message||'Unable to start'); }
  }
  function stop(){ mediaRef.current?.stop(); setStatus('idle'); }
  function reset(){ setAudioUrl(undefined); setDuration(0); setStatus('idle'); }
  function setFromFile(file: File){ setAudioUrl(URL.createObjectURL(file)); setStatus('uploading'); }
  return { status, duration, audioUrl, error, start, stop, reset, setFromFile } as Recorder;
}
```

---

## 13) Migration Plan (low risk)

1. **Create `/adapters`, `/services`, `/types`, `/lib` folders**.
2. Move `computeMetrics` → `/lib/metrics.ts`; export and unit‑test.
3. Replace inline recorder with **adapter hook**; switch `SessionControls` to receive `recorder` via props.
4. Wrap app in `ErrorBoundary`; add `LoggerProvider`.
5. Introduce TanStack Query for `/asr` & `/llm`.
6. Add Playwright test for three flows: record/stop, deny + upload, upload only.
7. Add `LlmPanel` behind feature flag; lazy‑load.

---

## 14) Definition of Done (Robustness)

* No runtime crashes on mic deny/HTTP/sandbox.
* Upload path always available; object URLs revoked on unmount.
* Charts and tabs never overflow; zero horizontal scroll at ≥1280px.
* Unit + component + e2e tests pass locally (CI optional).
* Telemetry events captured for record/ASR/LLM with durations.

---

**Next**: Want me to refactor the current canvas component to the **adapter pattern + providers** described above? I can produce the updated file in one pass.
