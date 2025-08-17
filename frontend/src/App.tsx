import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Award,
  Target,
  Calendar as CalendarIcon,
  TrendingUp,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Headphones,
  Activity,
  Wifi,
  WifiOff,
  Loader2,
} from "lucide-react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
} from "recharts";
import {
  apiGet,
  clsx,
  scoreColor,
  badgeColorByScore,
  statusDotColor,
} from "./utils";
import AudioRecorder from "./components/AudioRecorder";

/**
 * Voice Training UI – Single-file preview component
 * -------------------------------------------------
 * Drop-in preview for the app UI described in the spec. This file intentionally packs
 * all components into one TSX for quick copy/paste and iterative refinement.
 * In your real project, split components under `/frontend/src/components/*`.
 *
 * Tech assumptions:
 * - React 18 + TypeScript + Tailwind CSS
 * - Optional: lucide-react, recharts present in the project dev deps
 * - Backend FastAPI on http://localhost:8000; Frontend on http://localhost:3000
 *
 * What you get:
 * - Layout matching the spec (Header → Main (Left: Dashboard+Recorder+Transcription, Right: SessionControls+TrainingPlan) → Footer)
 * - WebSocket wiring with status indicator + minimal reconnect
 * - AudioRecorder with 20-bar live visualization and permission handling
 * - Dashboard cards + charts (mock-friendly, data-driven via props)
 * - SessionControls with clear states and ARIA labels
 * - TrainingPlanView with week navigation, completion checkboxes, and TTS playback
 * - Skeletons, toasts, a basic ErrorBoundary, and accessible interactions
 */

// ------------------------- Types -------------------------
export interface User {
  id: string;
  name: string;
  cefrLevel: "A1" | "A2" | "B1" | "B2" | "C1" | "C2";
  streakDays: number;
  latestScore: number;
  totalSessions: number;
}

export interface Session {
  id: string;
  startedAt: string;
  status: "ready" | "active" | "recording";
}

export interface AssessmentResult {
  pronunciationAccuracy: number; // 0..100
  wordAccuracy: number; // 0..100
  speakingPaceWPM: number; // words per minute
  cefrLevel: User["cefrLevel"];
}

export interface TrainingExercise {
  id: string;
  description: string;
  difficulty: "Easy" | "Medium" | "Hard";
  focus: "Pronunciation" | "Pacing" | "Fluency" | "Comprehension";
  completed: boolean;
  referenceText?: string;
}

export interface TrainingWeek {
  weekNumber: number;
  exercises: TrainingExercise[];
}

export interface TrainingPlan {
  userId: string;
  weeks: TrainingWeek[];
}

export type ConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";

export interface AppState {
  user: User | null;
  currentSession: Session | null;
  trainingPlan: TrainingPlan | null;
  isRecording: boolean;
  transcription: string;
  assessmentResult: AssessmentResult | null;
  connectionStatus: ConnectionStatus;
  activeExerciseId: string | null;
}

// ------------------------- Utilities -------------------------

// Define ToastItem used by useToasts
interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone?: "info" | "success" | "error" | "warning";
}

function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const push = useCallback(
    (t: Omit<ToastItem, "id">) => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev, { id, ...t }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((x) => x.id !== id));
      }, 3500);
    },
    []
  );

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((x) => x.id !== id));
  }, []);

  return { toasts, push, remove } as const;
}

function ToastViewport({ toasts, onClose }: { toasts: ToastItem[]; onClose: (id: number) => void }) {
  return (
    <div className="fixed z-[60] bottom-4 right-4 flex flex-col gap-2">{
      toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          aria-live="polite"
          className={clsx(
            "w-80 rounded-xl border shadow-lg p-3 backdrop-blur bg-white/90 dark:bg-slate-900/80",
            t.tone === "success" && "border-emerald-300",
            t.tone === "error" && "border-rose-300",
            t.tone === "warning" && "border-amber-300",
            (!t.tone || t.tone === "info") && "border-slate-200"
          )}
        >
          <div className="flex items-start gap-3">
            <div className={clsx("mt-1 h-2 w-2 rounded-full", t.tone === "success" && "bg-emerald-500", t.tone === "error" && "bg-rose-500", t.tone === "warning" && "bg-amber-500", (!t.tone || t.tone === "info") && "bg-slate-400")}></div>
            <div className="flex-1">
              <p className="font-medium text-slate-900 dark:text-slate-100">{t.title}</p>
              {t.description && (
                <p className="text-sm text-slate-600 dark:text-slate-300">{t.description}</p>
              )}
            </div>
            <button aria-label="Close" className="text-slate-400 hover:text-slate-700" onClick={() => onClose(t.id)}>
              <XCircle size={18} />
            </button>
          </div>
        </div>
      ))
    }</div>
  );
}

// ------------------------- Error Boundary -------------------------
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error?: any }> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }
  componentDidCatch(error: any) {
    console.error("UI error:", error);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 m-6 border rounded-xl bg-rose-50 border-rose-200 text-rose-800">
          <div className="flex items-center gap-2 mb-2"><AlertTriangle /> <span className="font-semibold">Something went wrong.</span></div>
          <p className="text-sm">Try reloading the page. If the issue persists, check the console for details.</p>
        </div>
      );
    }
    return this.props.children as any;
  }
}

// ------------------------- WebSocket hook -------------------------
function useTrainingSocket(handlers: {
  onTranscription: (text: string, confidence?: number) => void;
  onSessionStatus: (status: string, message?: string) => void;
  onOpen?: () => void;
  onClose?: (ev?: CloseEvent) => void;
}) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);

  useEffect(() => {
    let alive = true;

    function connect() {
      try {
        setStatus("connecting");
        const ws = new WebSocket("ws://localhost:8000/ws");
        wsRef.current = ws;
        ws.onopen = () => {
          if (!alive) return;
          retryRef.current = 0;
          setStatus("connected");
          handlers.onOpen?.();
        };
        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data);
            if (msg?.type === "transcription") {
              handlers.onTranscription(msg.data?.text ?? "", msg.data?.confidence);
            } else if (msg?.type === "session_status") {
              handlers.onSessionStatus(msg.data?.status ?? "", msg.data?.message);
            }
          } catch (e) {
            console.warn("WS parse error", e);
          }
        };
        ws.onerror = () => {
          setStatus("error");
        };
        ws.onclose = (ev) => {
          if (!alive) return;
          setStatus("disconnected");
          handlers.onClose?.(ev);
          const delay = Math.min(4000, 500 * Math.pow(2, retryRef.current++));
          setTimeout(() => alive && connect(), delay);
        };
      } catch (e) {
        console.error("WS connect failed", e);
        setStatus("error");
      }
    }

    connect();
    return () => {
      alive = false;
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, []); // eslint-disable-line

  const send = useCallback((obj: any) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  return { status, send } as const;
}

// ------------------------- Header -------------------------
function Header({ user, status, apiHealthy }: { user: User | null; status: ConnectionStatus; apiHealthy: boolean }) {
  return (
    <header className="sticky top-0 z-50 backdrop-blur-lg bg-slate-900/70 border-b border-slate-700/50">
      <div className="mx-auto max-w-7xl px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={clsx("h-2.5 w-2.5 rounded-full", statusDotColor(status))} aria-label={`Connection ${status}`}></div>
          <div className="flex items-center gap-2 text-slate-300">
            {status === "connected" ? <Wifi size={18} /> : <WifiOff size={18} />}
            <span className="font-semibold text-slate-200">VoiceCoach</span>
            <span className="text-xs px-2 py-0.5 rounded-full border bg-slate-800 border-slate-700">{status}</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <div className="hidden sm:flex items-center gap-2 text-slate-400">
            <Activity size={18} />
            <span className={clsx("px-2 py-0.5 rounded-full border", apiHealthy ? "border-emerald-300 text-emerald-700 bg-emerald-50" : "border-rose-300 text-rose-700 bg-rose-50")}>{apiHealthy ? "API healthy" : "API down"}</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-slate-100 font-medium leading-tight">{user?.name ?? "Guest"}</div>
              <div className="text-slate-400 text-xs">{user ? `CEFR ${user.cefrLevel} • ${user.streakDays} day streak` : "Not signed in"}</div>
            </div>
            <div className="h-9 w-9 rounded-full bg-gradient-to-br from-sky-500 to-indigo-500" aria-hidden />
          </div>
        </div>
      </div>
    </header>
  );
}

// ------------------------- Dashboard -------------------------
function StatCard({ title, value, icon: Icon, toneClass }: { title: string; value: string; icon: any; toneClass?: string }) {
  return (
    <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs uppercase tracking-wider text-slate-400 font-medium">{title}</p>
        <Icon className="text-slate-500" size={18} />
      </div>
      <div className={clsx("text-3xl font-bold tracking-tight", toneClass)}>{value}</div>
    </div>
  );
}

function Dashboard({ user, assessment, history }: { user: User | null; assessment: AssessmentResult | null; history: Array<{ date: string; acc: number; wer: number }> }) {
  const latestScore = user?.latestScore ?? 0;
  const cefr = user?.cefrLevel ?? "A1";
  const streak = user?.streakDays ?? 0;
  const sessions = user?.totalSessions ?? 0;

  return (
    <section className="space-y-6">
      {/* Progress Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard title="CEFR Level" value={cefr} icon={Award} toneClass="text-indigo-600" />
        <StatCard title="Latest Score" value={`${latestScore}%`} icon={Target} toneClass={scoreColor(latestScore)} />
        <StatCard title="Streak Days" value={`${streak}`} icon={CalendarIcon} toneClass="text-sky-600" />
        <StatCard title="Practice Sessions" value={`${sessions}`} icon={TrendingUp} toneClass="text-emerald-600" />
      </div>

      {/* Current Assessment */}
      {assessment && (
        <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-100">Current Assessment</h3>
            <span className={clsx("text-xs px-2 py-0.5 rounded-full border", badgeColorByScore(assessment.pronunciationAccuracy))}>CEFR {assessment.cefrLevel}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Metric label="Pronunciation" value={assessment.pronunciationAccuracy} suffix="%" />
            <Metric label="Word Accuracy" value={assessment.wordAccuracy} suffix="%" />
            <Metric label="Pace" value={assessment.speakingPaceWPM} suffix=" WPM" />
            <div className="rounded-xl border p-3 border-slate-700/80 bg-slate-800/70">
              <p className="text-xs text-slate-400 mb-1">Status</p>
              <div className="flex items-center gap-2 text-slate-200"><CheckCircle2 className="text-emerald-500" size={18} /> <span className="text-sm">Analyzed</span></div>
            </div>
          </div>
        </div>
      )}

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Accuracy trend (7d MA)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={history} margin={{ left: 6, right: 16, top: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="acc" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
              <XAxis dataKey="date" fontSize={12} tickMargin={6} stroke="#64748b" />
              <YAxis domain={[0, 100]} fontSize={12} tickMargin={6} stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgba(5, 15, 25, 0.7)",
                  borderColor: "#334155",
                  borderRadius: "0.75rem",
                  backdropFilter: "blur(4px)",
                }}
                labelStyle={{ color: "#cbd5e1" }}
              />
              <Area type="monotone" dataKey="acc" stroke="#22c55e" fillOpacity={1} fill="url(#acc)" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Error rate (WER) trend">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={history} margin={{ left: 6, right: 16, top: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
              <XAxis dataKey="date" fontSize={12} tickMargin={6} stroke="#64748b" />
              <YAxis domain={[0, 100]} fontSize={12} tickMargin={6} stroke="#64748b" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "rgba(5, 15, 25, 0.7)",
                  borderColor: "#334155",
                  borderRadius: "0.75rem",
                  backdropFilter: "blur(4px)",
                }}
                labelStyle={{ color: "#cbd5e1" }}
              />
              <Bar dataKey="wer" fill="#818cf8" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </section>
  );
}

function Metric({ label, value, suffix = "" }: { label: string; value: number; suffix?: string }) {
  return (
    <div className="rounded-xl border p-3 border-slate-700/80 bg-slate-800/70">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={clsx("text-xl font-semibold", scoreColor(value))}>{value}{suffix}</p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-slate-200">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// Add simple HTTP helpers for JSON POSTs
async function postJson<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`http://localhost:8000${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}
async function postFile<T>(path: string, file: File | Blob, filename = "audio.wav", field = "file"): Promise<T> {
  const fd = new FormData();
  fd.append(field, file, filename);
  const res = await fetch(`http://localhost:8000${path}`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

// Filler lexicon
const FILLERS = ["um","uh","like","you","you know","actually","basically","literally","so","i","i mean"];

// (Inline AudioRecorder removed; imported component is used instead.)

// ------------------------- Session Controls -------------------------
function SessionControls({ state, onStart, onEnd }: { state: Session["status"] | "ready"; onStart: () => void; onEnd: () => void }) {
  const statusMap: Record<string, { label: string; color: string }> = {
    ready: { label: "Ready to start", color: "bg-slate-400" },
    active: { label: "Session active", color: "bg-sky-500" },
    recording: { label: "Listening…", color: "bg-rose-500 animate-pulse" },
  };
  const meta = statusMap[state] ?? statusMap.ready;

  return (
    <section className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-200">Session Controls</h3>
        <div className="flex items-center gap-2 text-sm text-slate-400"><Headphones size={16} /> Guided Practice</div>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <span className={clsx("h-2.5 w-2.5 rounded-full", meta.color)} />
          <span className="text-slate-300">{meta.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onStart} className="px-4 py-2 rounded-lg bg-sky-600 text-white font-semibold hover:bg-sky-700 border border-sky-700 transition-all duration-150 hover:scale-105 active:scale-95"><Play size={16} className="inline mr-1 -mt-0.5"/> Start</button>
          <button onClick={onEnd} className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 border border-slate-600 text-slate-200 font-semibold transition-all duration-150 hover:scale-105 active:scale-95"><Pause size={16} className="inline mr-1 -mt-0.5"/> End</button>
        </div>
      </div>
      <div className="mt-4 text-sm text-slate-400 leading-relaxed">
        Follow the on-screen prompts. Speak clearly. You can pause anytime; your progress is saved per step.
      </div>
    </section>
  );
}

// ------------------------- Training Plan View -------------------------
function TrainingPlanView({ plan, onToggle, onPlay, currentWeek, onPrev, onNext, activeExerciseId, onSetActive }: {
  plan: TrainingPlan | null;
  currentWeek: number;
  onPrev: () => void;
  onNext: () => void;
  onToggle: (week: number, id: string) => void;
  onPlay: (text: string) => void;
  activeExerciseId: string | null;
  onSetActive: (id: string) => void;
}) {
  if (!plan) return <Skeleton title="Training Plan" lines={5} />;
  const week = plan.weeks.find((w) => w.weekNumber === currentWeek) ?? plan.weeks[0];
  return (
    <section className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-200">Training Plan – Week {week.weekNumber}</h3>
        <div className="flex items-center gap-2">
          <button aria-label="Previous week" onClick={onPrev} className="p-2 rounded-lg border border-slate-700 hover:bg-slate-700/50 transition-all"><ChevronLeft size={18} /></button>
          <button aria-label="Next week" onClick={onNext} className="p-2 rounded-lg border border-slate-700 hover:bg-slate-700/50 transition-all"><ChevronRight size={18} /></button>
        </div>
      </div>
      <div className="space-y-3">
        {week.exercises.map((ex) => (
          <div 
            key={ex.id}
            className={clsx(
              "rounded-xl border p-3 transition-all duration-200",
              activeExerciseId === ex.id
                ? "border-sky-500 bg-sky-900/30 ring-2 ring-sky-500"
                : "border-slate-700/80 bg-slate-800/50 hover:bg-slate-700/50"
            )}
            onClick={() => onSetActive(ex.id)}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <input
                  id={`ex-${ex.id}`}
                  type="checkbox"
                  checked={ex.completed}
                  onChange={() => onToggle(week.weekNumber, ex.id)}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-700 text-sky-500 focus:ring-sky-500 focus:ring-offset-slate-800"
                />
                <label htmlFor={`ex-${ex.id}`} className="font-medium text-slate-200">Step {ex.id}</label>
                <span className="text-xs px-2 py-0.5 rounded-full border border-slate-700 bg-slate-900/60 font-medium">{ex.difficulty}</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-slate-700 bg-slate-900/60 font-medium">{ex.focus}</span>
              </div>
              <button onClick={() => onPlay(ex.referenceText ?? ex.description)} className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 border border-indigo-700 transition-all duration-150 hover:scale-105 active:scale-95 text-sm"><Play size={14} className="inline mr-1.5 -mt-0.5"/> Play Reference</button>
            </div>
            <p className="mt-2 text-sm text-slate-300 pl-7">{ex.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Skeleton({ title, lines = 3 }: { title?: string; lines?: number }) {
  return (
    <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      {title && <div className="h-5 w-40 mb-4 bg-slate-700/50 rounded animate-pulse" />}
      <div className="space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-4 bg-slate-700/50 rounded animate-pulse" style={{ width: `${100 - i*10}%` }}/>
        ))}
      </div>
    </div>
  );
}

// ------------------------- Transcription Panel -------------------------
function TranscriptionPanel({ text, confidence }: { text: string; confidence?: number }) {
  return (
    <section className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-slate-200">Live Transcription</h3>
        {typeof confidence === "number" && (
          <span className="text-xs text-slate-400 font-medium">Confidence: {(confidence * 100).toFixed(0)}%</span>
        )}
      </div>
      <pre className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200 bg-slate-900/50 rounded-xl p-3 border border-slate-700/50 min-h-[96px]">
        {text || <span className="text-slate-500">Start speaking to see transcription here…</span>}
      </pre>
    </section>
  );
}

// ------------------------- App (Root) -------------------------
export default function App() {
  const { toasts, push, remove } = useToasts();
  const [state, setState] = useState<AppState>({
    user: null,
    currentSession: null,
    trainingPlan: null,
    isRecording: false,
    transcription: "",
    assessmentResult: null,
    connectionStatus: "connecting",
    activeExerciseId: null,
  });
  const [isFocusMode, setFocusMode] = useState(false);
  const [apiHealthy, setApiHealthy] = useState<boolean>(true);
  const [loading, setLoading] = useState(true);
  const [currentWeek, setCurrentWeek] = useState(1);
  const [transcriptionConfidence, setTranscriptionConfidence] = useState<number | undefined>(undefined);
  const [recordStartedAt, setRecordStartedAt] = useState<number | null>(null);
  const [exerciseMetrics, setExerciseMetrics] = useState<Record<string, { words: number; wpm: number; fillerPerMin: number; bannedHits?: number; wer?: number; score?: number; feedback?: string[] }>>({});
  const lastPartialAtRef = useRef<number | null>(null);

  // Compute simple metrics from transcript and seconds
  const computeLocalMetrics = (text: string, seconds: number, bannedWords?: string[]) => {
    const t = (text || "").toLowerCase().trim();
    const words = t ? t.split(/\s+/).length : 0;
    const wpm = seconds > 0 ? Math.round((words / seconds) * 60) : 0;
    // filler count
    const fillerCount = FILLERS.reduce((acc, f) => {
      const re = new RegExp(`\\b${f.replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")}\\b`, "g");
      return acc + (t.match(re)?.length || 0);
    }, 0);
    const fillerPerMin = seconds > 0 ? +(fillerCount / (seconds / 60)).toFixed(1) : 0;
    const banned = bannedWords || [];
    const bannedHits = banned.reduce((acc, w) => acc + (t.match(new RegExp(`\\b${w}\\b`, "g"))?.length || 0), 0);
    return { words, wpm, fillerPerMin, bannedHits };
  };

  // Optionally compute WER from backend for scripted drills
  const computeWerIfScripted = async (reference?: string, hypothesis?: string) => {
    if (!reference || !hypothesis) return undefined;
    try {
      const r = await postJson<{ wer: number }>("/metrics/wer", { reference, hypothesis });
      return r.wer;
    } catch {
      return undefined;
    }
  };

  // Mock-friendly history for charts; replace with backend analytics when available
  const history = useMemo(() => {
    const days = 14;
    const out: Array<{ date: string; acc: number; wer: number }> = [];
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const date = d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const acc = 70 + Math.round(Math.sin(i / 2) * 10 + Math.random() * 8);
      const wer = Math.max(0, 100 - acc + Math.round(Math.random() * 6));
      out.push({ date, acc: Math.min(100, Math.max(0, acc)), wer: Math.min(100, Math.max(0, wer)) });
    }
    return out;
  }, []);

  // WebSocket hookup
  const socket = useTrainingSocket({
    onTranscription: (text, conf) => {
      setState((s) => ({ ...s, transcription: text }));
      setTranscriptionConfidence(conf);
      lastPartialAtRef.current = Date.now();
    },
    onSessionStatus: (status, message) => {
      setState((s) => ({
        ...s,
        currentSession: s.currentSession
          ? { ...s.currentSession, status: mapBackendStatus(status) }
          : { id: "session", startedAt: new Date().toISOString(), status: mapBackendStatus(status) },
        isRecording: status === "recording",
      }));
      if (message) push({ title: message, tone: "info" });
    },
    onOpen: () => setState((s) => ({ ...s, connectionStatus: "connected" })),
    onClose: () => setState((s) => ({ ...s, connectionStatus: "disconnected" })),
  });

  // Health check + initial data
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const health = await apiGet<{ status: string }>("/health");
        if (!active) return;
        setApiHealthy(health.status === "ok" || health.status === "healthy");
        const user = await bootstrapUser();
        const plan = await apiGet<TrainingPlan>(`/training-plans/${user.id}`);
        if (!active) return;
        const ensuredPlan = ensurePlan(plan);
        setState((s) => ({ ...s, user, trainingPlan: ensuredPlan, connectionStatus: socket.status }));
        if (ensuredPlan && ensuredPlan.weeks && ensuredPlan.weeks.length > 0) {
          setCurrentWeek(ensuredPlan.weeks[0].weekNumber);
        } else {
          setCurrentWeek(1);
        }
      } catch (e) {
        console.warn("bootstrap failed", e);
        if (!active) return;
        setApiHealthy(false);
        // Fallback mock user/plan to allow UI exploration
        const user: User = { id: "demo", name: "Rakesh", cefrLevel: "B2", streakDays: 6, latestScore: 82, totalSessions: 24 };
        const plan = mockPlan(user.id);
        setState((s) => ({ ...s, user, trainingPlan: plan, connectionStatus: socket.status }));
        setCurrentWeek(plan.weeks[0]?.weekNumber ?? 1);
        push({ title: "Running in demo mode (API unavailable)", tone: "warning" });
      } finally {
        setLoading(false);
      }
    })();

    const t = setInterval(async () => {
      try {
        const h = await apiGet<{ status: string }>("/health");
        setApiHealthy(h.status === "ok" || h.status === "healthy");
      } catch {
        setApiHealthy(false);
      }
    }, 5000);

    return () => {
      active = false;
      clearInterval(t);
    };
  }, []); // eslint-disable-line

  // Session actions
  const startSession = useCallback(async () => {
    try {
      setState((s) => ({ ...s, currentSession: { id: crypto.randomUUID(), startedAt: new Date().toISOString(), status: "active" } }));
      socket.send({ type: "session_start", data: { userId: state.user?.id } });
      push({ title: "Session started", tone: "success" });
      setFocusMode(true);
      // default active exercise to first item when entering focus
      if (!state.activeExerciseId) {
        const firstId = state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
        if (firstId) setState((s) => ({ ...s, activeExerciseId: firstId }));
      }
      // Start WS diagnostics watchdog for partials
      lastPartialAtRef.current = null;
      setTimeout(() => {
        if (!lastPartialAtRef.current) {
          push({ title: "No live partials yet", description: "We’ll still compute final transcript on Stop/End.", tone: "warning" });
        }
      }, 2000);
    } catch (e) {
      push({ title: "Failed to start session", tone: "error" });
    }
  }, [socket, state.user?.id, push, state.activeExerciseId, state.trainingPlan]);

  const endSession = useCallback(async () => {
    try {
      socket.send({ type: "session_end", data: {} });
      setState((s) => ({ ...s, currentSession: s.currentSession ? { ...s.currentSession, status: "ready" } : null, isRecording: false }));
      push({ title: "Session ended", tone: "info" });
      setFocusMode(false);
      // On end, finalize metrics for active exercise if we have transcript
      const exId = state.activeExerciseId || state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
      if (exId) {
        const seconds = recordStartedAt ? Math.max(1, Math.round((Date.now() - recordStartedAt) / 1000)) : 60;
        const m = computeLocalMetrics(state.transcription, seconds);
        const refText = state.trainingPlan?.weeks?.flatMap((w) => w.exercises)?.find((e) => e.id === exId)?.referenceText;
        const wer = await computeWerIfScripted(refText, state.transcription);
        setExerciseMetrics((prev) => ({ ...prev, [exId]: { ...m, wer } }));
      }
    } catch (e) {
      push({ title: "Failed to end session", tone: "error" });
    }
  }, [socket, push, state.activeExerciseId, state.trainingPlan, state.transcription, recordStartedAt]);

  const handleAudioChunk = useCallback(
    async (buf: ArrayBuffer) => {
      // This now receives Int16 PCM @16kHz mono from AudioRecorder
      try {
        const bytes = new Uint8Array(buf);
        let binary = "";
        for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
        const b64 = btoa(binary);
        socket.send({ type: "pcm_chunk", data: { chunk: b64 } });
      } catch {
        // Fallback HTTP is not applicable for PCM streaming; ignore
      }
    },
    [socket]
  );

  const toggleExercise = useCallback((weekNumber: number, id: string) => {
    setState((s) => ({
      ...s,
      trainingPlan: s.trainingPlan
        ? {
            ...s.trainingPlan,
            weeks: s.trainingPlan.weeks.map((w) =>
              w.weekNumber === weekNumber
                ? { ...w, exercises: w.exercises.map((ex) => (ex.id === id ? { ...ex, completed: !ex.completed } : ex)) }
                : w
            ),
          }
        : s.trainingPlan,
    }));
  }, []);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      push({ title: "TTS not supported", description: "Your browser doesn't support speech synthesis.", tone: "warning" });
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "en-US";
    utter.rate = 1.0;
    utter.pitch = 1.0;
    speechSynthesis.speak(utter);
  }, [push]);

  // Loading frame
  if (loading) {
    return (
      <div className="min-h-dvh bg-gradient-to-b from-slate-50 to-white dark:from-slate-950 dark:to-slate-900 text-slate-900 dark:text-slate-100">
        <Header user={null} status={socket.status} apiHealthy={apiHealthy} />
        <main className="mx-auto max-w-7xl px-4 py-8 grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton title="Dashboard" lines={6} />
            <Skeleton title="Audio Recorder" lines={4} />
            <Skeleton title="Live Transcription" lines={5} />
          </div>
          <div className="space-y-4">
            <Skeleton title="Session Controls" lines={3} />
            <Skeleton title="Training Plan" lines={6} />
          </div>
        </main>
      </div>
    );
  }

  const sessionStatus = state.currentSession?.status ?? "ready";

  return (
    <ErrorBoundary>
      <div className="min-h-dvh bg-slate-900 text-slate-100 font-sans">
        <Header user={state.user} status={socket.status} apiHealthy={apiHealthy} />
        <main className={clsx(
          "mx-auto max-w-7xl px-4 py-6 grid gap-6 transition-all duration-300",
          isFocusMode ? "lg:grid-cols-1" : "lg:grid-cols-3"
        )}>
          {/* Main Content Column */}
          <div className="lg:col-span-2 space-y-6">
            {!isFocusMode && <Dashboard user={state.user} assessment={state.assessmentResult} history={history} />}
            <AudioRecorder
              isActive={state.isRecording}
              onChunk={handleAudioChunk}
              onStart={() => {
                setState((s) => ({ ...s, isRecording: true }));
                setRecordStartedAt(Date.now());
                socket.send({ type: "session_status", data: { status: "recording" } });
              }}
              onStop={() => {
                setState((s) => ({ ...s, isRecording: false }));
                socket.send({ type: "session_status", data: { status: "active" } });
                // Compute quick metrics on stop for current exercise
                const exId = state.activeExerciseId || state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
                if (exId) {
                  const seconds = recordStartedAt ? Math.max(1, Math.round((Date.now() - recordStartedAt) / 1000)) : 60;
                  const m = computeLocalMetrics(state.transcription, seconds);
                  setExerciseMetrics((prev) => ({ ...prev, [exId]: { ...prev[exId], ...m } }));
                }
              }}
              onBlob={async (blob) => {
                try {
                  // Upload fallback to /asr
                  const r = await postFile<{ text: string; duration_sec: number }>("/asr", blob, "take.wav");
                  // Update transcript and recompute badges
                  setState((s) => ({ ...s, transcription: r.text || s.transcription }));
                  const exId = state.activeExerciseId || state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
                  if (exId) {
                    const seconds = Math.max(1, Math.round(r.duration_sec || (recordStartedAt ? (Date.now() - recordStartedAt) / 1000 : 60)));
                    const refText = state.trainingPlan?.weeks?.flatMap((w) => w.exercises)?.find((e) => e.id === exId)?.referenceText;
                    const m = computeLocalMetrics(r.text || state.transcription, seconds);
                    const wer = await computeWerIfScripted(refText, r.text || state.transcription);
                    setExerciseMetrics((prev) => ({ ...prev, [exId]: { ...m, wer } }));
                  }
                  push({ title: "Transcript updated", tone: "success" });
                } catch {
                  push({ title: "Upload ASR failed", tone: "error" });
                }
              }}
              disabled={sessionStatus === "ready"}
            />
            <TranscriptionPanel text={state.transcription} confidence={transcriptionConfidence} />
          </div>
          {/* Sidebar Column */}
          <div className={clsx("space-y-6", isFocusMode ? "lg:col-start-1 lg:row-start-1" : "")}>            
            <SessionControls state={sessionStatus} onStart={startSession} onEnd={endSession} />
            <TrainingPlanView
              plan={state.trainingPlan}
              currentWeek={currentWeek}
              onPrev={() => setCurrentWeek((w) => Math.max(1, w - 1))}
              onNext={() => setCurrentWeek((w) => Math.min((state.trainingPlan?.weeks.length ?? 1), w + 1))}
              onToggle={toggleExercise}
              onPlay={speak}
              activeExerciseId={state.activeExerciseId}
              onSetActive={(id) => setState(s => ({ ...s, activeExerciseId: id }))}
            />
            {/* Recent metrics badges for active exercise */}
            {(() => {
              const exId = state.activeExerciseId || state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
              const m = exId ? exerciseMetrics[exId] : undefined;
              if (!m) return null;
              return (
                <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 ring-1 ring-inset ring-slate-700/50">
                  <div className="text-sm font-semibold mb-2">Last Take Metrics</div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <span className="px-2 py-1 rounded-lg border border-slate-700 bg-slate-900/50">Words: <b>{m.words}</b></span>
                    <span className="px-2 py-1 rounded-lg border border-slate-700 bg-slate-900/50">WPM: <b>{m.wpm}</b></span>
                    <span className="px-2 py-1 rounded-lg border border-slate-700 bg-slate-900/50">Fillers/min: <b>{m.fillerPerMin}</b></span>
                    {typeof m.bannedHits === 'number' && (
                      <span className={clsx("px-2 py-1 rounded-lg border bg-slate-900/50", m.bannedHits>0?"border-rose-600 text-rose-300":"border-slate-700")}>Banned: <b>{m.bannedHits}</b></span>
                    )}
                    {typeof m.wer === 'number' && (
                      <span className="px-2 py-1 rounded-lg border border-slate-700 bg-slate-900/50">WER: <b>{(m.wer*100).toFixed(1)}%</b></span>
                    )}
                    {typeof m.score === 'number' && (
                      <span className="px-2 py-1 rounded-lg border border-slate-700 bg-slate-900/50">Score: <b>{m.score}</b></span>
                    )}
                  </div>
                  {m.feedback && m.feedback.length>0 && (
                    <ul className="mt-2 text-xs text-slate-300 list-disc pl-4 space-y-1">
                      {m.feedback.map((f,i)=>(<li key={i}>{f}</li>))}
                    </ul>
                  )}
                </div>
              );
            })()}
            {/* LLM Panel */}
            {(() => {
              const [skillOptions, cefrOptions] = [["articulation","descriptive","emotion","instructional","narrative"],["A2","B1","B2","C1"]];
              return (
                <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 ring-1 ring-inset ring-slate-700/50 space-y-3">
                  <div className="text-sm font-semibold">LLM Generator</div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <select id="llm-skill" className="bg-slate-950 border border-slate-800 rounded-md p-2">
                      {skillOptions.map(s=> <option key={s} value={s}>{s}</option>)}
                    </select>
                    <select id="llm-cefr" className="bg-slate-950 border border-slate-800 rounded-md p-2" defaultValue={state.user?.cefrLevel||"B2"}>
                      {cefrOptions.map(c=> <option key={c} value={c}>{c}</option>)}
                    </select>
                    <input id="llm-topic" placeholder="Topic (optional)" className="bg-slate-950 border border-slate-800 rounded-md p-2" />
                  </div>
                  <div className="flex gap-2">
                    <button className="px-3 py-2 rounded-lg bg-sky-600 border border-sky-700 text-white text-xs" onClick={async()=>{
                      const skill=(document.getElementById('llm-skill') as HTMLSelectElement).value;
                      const cefr=(document.getElementById('llm-cefr') as HTMLSelectElement).value;
                      const topic=(document.getElementById('llm-topic') as HTMLInputElement).value;
                      try{
                        const data = await postJson<{drills:any[]}>("/llm/generate-drills", {skill, cefr, topic, count:3, constraints:{banned_words:["delicious","tasty"]}});
                        // Insert into current week's exercises
                        const drills = data.drills||[];
                        setState((s)=>{
                          if(!s.trainingPlan) return s;
                          const exs = s.trainingPlan.weeks[0].exercises.slice();
                          drills.forEach((d:any)=>{
                            exs.push({ id: d.id || crypto.randomUUID(), description: d.prompt || d.title, difficulty: "Medium", focus: (d.type||"Fluency").toString().charAt(0).toUpperCase()+ (d.type||"fluency").toString().slice(1), completed:false, referenceText: d.script });
                          });
                          const weeks=s.trainingPlan.weeks.slice();
                          weeks[0]={...weeks[0], exercises: exs};
                          return {...s, trainingPlan:{...s.trainingPlan,weeks}};
                        });
                        push({ title:"Inserted drills", tone:"success"});
                      }catch{ push({ title:"Failed to generate drills", tone:"error"}); }
                    }}>Generate & Insert</button>
                    <button className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-xs" onClick={async()=>{
                      const exId = state.activeExerciseId || state.trainingPlan?.weeks?.[0]?.exercises?.[0]?.id;
                      if(!exId) return;
                      const m = exerciseMetrics[exId];
                      try{
                        const r = await postJson<{score:number; feedback:string[]; next_drill_hint?:string}>("/llm/critique", { transcript: state.transcription, metrics: m||{}, cefr: state.user?.cefrLevel||"B2", skill: "narrative" });
                        setExerciseMetrics(prev=> ({...prev, [exId]: {...(prev[exId]||{}), score:r.score, feedback:r.feedback}}));
                        if(r.next_drill_hint) push({ title:"Coach hint", description:r.next_drill_hint, tone:"info"});
                      }catch{ push({ title:"Critique failed", tone:"error"}); }
                    }}>Critique Last Take</button>
                    <button className="px-3 py-2 rounded-lg bg-slate-700 border border-slate-600 text-xs" onClick={async()=>{
                      try{
                        const topic=(document.getElementById('llm-topic') as HTMLInputElement)?.value || 'general';
                        const r = await postJson<{questions:string[]}>("/llm/followups", { topic, cefr: state.user?.cefrLevel||"B2", count:5 });
                        push({ title:"Follow-ups", description: (r.questions||[]).slice(0,2).join(" | ") || "Generated" , tone:"info"});
                      }catch{ push({ title:"Follow-ups failed", tone:"error"}); }
                    }}>Follow-ups</button>
                  </div>
                </div>
              );
            })()}
          </div>
        </main>
        <footer className="mx-auto max-w-7xl px-4 pb-8 pt-2 text-xs text-slate-400 flex items-center justify-center gap-2">
          <Loader2 className="animate-spin" size={14} />
          <span>FastAPI @ <a className="underline hover:text-sky-400" href="http://localhost:8000/docs" target="_blank" rel="noreferrer">/docs</a> • Frontend Vite dev @ <a className="underline hover:text-sky-400" href="http://localhost:3000" target="_blank" rel="noreferrer">/</a></span>
        </footer>
        <ToastViewport toasts={toasts} onClose={remove} />
      </div>
    </ErrorBoundary>
  );
}

// ------------------------- Helpers & mocks -------------------------
function mapBackendStatus(s: string): Session["status"] {
  const normalized = (s || "").toLowerCase();
  if (normalized === "recording" || normalized === "listening") return "recording";
  if (normalized === "active" || normalized === "started" || normalized === "start") return "active";
  if (normalized === "ready" || normalized === "ended" || normalized === "stopped") return "ready";
  return "ready";
}

async function bootstrapUser(): Promise<User> {
  try {
    // Replace with POST /users/ on first use if needed
    const user = await apiGet<User>("/users/demo");
    return user;
  } catch {
    // fallback demo
    return { id: "demo", name: "Rakesh", cefrLevel: "B2", streakDays: 6, latestScore: 82, totalSessions: 24 };
  }
}

function ensurePlan(plan: TrainingPlan | null): TrainingPlan | null {
  if (!plan) return plan;
  if (!plan.weeks?.length) return { ...plan, weeks: [mockWeek(1)] };
  return plan;
}

function mockPlan(userId: string): TrainingPlan {
  return {
    userId,
    weeks: [mockWeek(1), mockWeek(2), mockWeek(3)],
  };
}

function mockWeek(n: number): TrainingWeek {
  return {
    weekNumber: n,
    exercises: [
      { id: "1", description: "Shadow the sentence: 'The quick brown fox jumps over the lazy dog.'", difficulty: "Easy", focus: "Pronunciation", completed: false, referenceText: "The quick brown fox jumps over the lazy dog." },
      { id: "2", description: "Read a 90 WPM paragraph from a news article.", difficulty: "Medium", focus: "Pacing", completed: false },
      { id: "3", description: "Describe your day in 60 seconds with clear articulation.", difficulty: "Medium", focus: "Fluency", completed: false },
      { id: "4", description: "Listen and repeat 10 tricky minimal pairs (ship/sheep, bad/bed…).", difficulty: "Hard", focus: "Pronunciation", completed: false },
    ],
  };
}

/*
============================
Quick Test Stub (Vitest)
============================
import { describe, it, expect } from 'vitest';
import { scoreColor } from './App';

describe('scoreColor', () => {
  it('green for ≥85', () => {
    expect(scoreColor(90)).toContain('emerald');
  });
  it('yellow for 70–84', () => {
    expect(scoreColor(70)).toContain('amber');
    expect(scoreColor(84)).toContain('amber');
  });
  it('red for <70', () => {
    expect(scoreColor(69)).toContain('rose');
  });
});
*/
