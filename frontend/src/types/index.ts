// Main App Types
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
}

// Backend API Response Types (existing)
export interface BackendUser {
  user_id: number;
  username: string;
  streak: number;
  latest_score: number;
  cefr_level: string;
  analytics: AnalyticsData;
  history_count: number;
}

export interface AnalyticsData {
  accuracy: number[];
  wer: number[];
  moving_average?: number;
  month_over_month?: number;
}

export interface BackendSession {
  session_id: number;
  user_id: number;
}

export interface BackendTrainingPlan {
  plan_id?: number;
  plan: PlanData;
  current_week: number;
  week_steps: TrainingStep[];
  total_weeks: number;
}

export interface PlanData {
  weeks: number;
  daily_minutes: number;
  steps: TrainingStep[];
}

export interface TrainingStep {
  step_num: number;
  week: number;
  description: string;
  completed?: boolean;
  difficulty?: string;
  focus_area?: string;
}

export interface BackendAssessmentResult {
  phoneme_accuracy: number;
  word_error_rate: number;
  pace_wpm: number;
  overall_score: number;
  cefr_level: string;
}

export interface TranscriptionResult {
  transcript: string;
  confidence?: number;
}

// Health Status
export interface HealthStatus {
  status: string;
  database: boolean;
  llm: boolean;
  whisper: boolean;
  config_loaded: boolean;
}

// WebSocket Message Types
export interface WSMessage {
  type: 'audio_chunk' | 'session_start' | 'session_end' | 'transcription' | 'session_status';
  data: any;
}

export interface AudioChunk {
  audio: ArrayBuffer;
  timestamp: number;
}

// Component Props
export interface AudioVisualizerProps {
  isRecording: boolean;
  audioLevel: number;
}

export interface TrainingStepProps {
  step: TrainingStep;
  onComplete: (stepNum: number) => void;
  onPlay: (description: string) => void;
}

// Chart Data for Analytics
export interface ChartDataPoint {
  date: string;
  acc: number;
  wer: number;
}