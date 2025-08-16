import React, { useState, useRef, useCallback, useEffect } from 'react';
import { Mic, Pause, Volume2, AlertTriangle } from 'lucide-react';
import { clsx } from '../utils';

interface AudioRecorderProps {
  isActive: boolean;
  onChunk: (data: ArrayBuffer) => void; // Expects Int16 PCM @ 16kHz mono
  onStart: () => void;
  onStop: () => void;
  disabled?: boolean;
}

const TARGET_SAMPLE_RATE = 16000;

function floatTo16BitPCM(float32: Float32Array): Int16Array {
  const out = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}

function downsampleTo16k(buffer: Float32Array, inputSampleRate: number): Int16Array {
  if (inputSampleRate === TARGET_SAMPLE_RATE) {
    return floatTo16BitPCM(buffer);
  }
  if (inputSampleRate < TARGET_SAMPLE_RATE) {
    // Do not upsample; just pass through and let backend handle
    return floatTo16BitPCM(buffer);
  }
  const ratio = inputSampleRate / TARGET_SAMPLE_RATE;
  const newLen = Math.floor(buffer.length / ratio);
  const result = new Int16Array(newLen);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < newLen) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    const sample = accum / (count || 1);
    const s = Math.max(-1, Math.min(1, sample));
    result[offsetResult++] = s < 0 ? s * 0x8000 : s * 0x7fff;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({
  isActive,
  onChunk,
  onStart,
  onStop,
  disabled,
}) => {
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(0);
  const [bars, setBars] = useState<number[]>(Array.from({ length: 20 }, () => 0));
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const getBarColor = (value: number) => {
    if (value > 0.6) return 'from-amber-500 to-rose-500'; // Too loud
    if (value > 0.25) return 'from-emerald-500 to-green-400'; // Optimal
    return 'from-sky-500 to-indigo-400'; // Quiet
  };

  const visualize = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyser.getByteFrequencyData(dataArray);

    const buckets = 20;
    const bucketSize = Math.floor(bufferLength / buckets);
    const out: number[] = [];
    for (let i = 0; i < buckets; i++) {
      const start = i * bucketSize;
      const slice = dataArray.slice(start, start + bucketSize);
      const avg = slice.reduce((a, b) => a + b, 0) / Math.max(1, slice.length);
      out.push(avg / 255);
    }
    setBars(out);
    setLevel(out.reduce((a, b) => Math.max(a, b), 0));
    rafRef.current = requestAnimationFrame(visualize);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const AudioCtx: typeof AudioContext = (window as any).AudioContext || (window as any).webkitAudioContext;
      const ctx = new AudioCtx();
      audioCtxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // Visualizer
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      analyserRef.current = analyser;

      // PCM capture via ScriptProcessor (wide support)
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;
      source.connect(processor);
      processor.connect(ctx.destination); // required in some browsers

      processor.onaudioprocess = (e) => {
        try {
          const input = e.inputBuffer.getChannelData(0);
          const int16 = downsampleTo16k(input, ctx.sampleRate);
          if (int16.length > 0) {
            onChunk(int16.buffer);
          }
        } catch (_) {
          // ignore per-chunk errors
        }
      };

      visualize();
      onStart();
    } catch (e: any) {
      console.error(e);
      setError('Microphone permission denied or unsupported browser.');
    }
  }, [onChunk, onStart, visualize]);

  const stop = useCallback(() => {
    try {
      processorRef.current?.disconnect();
      sourceRef.current?.disconnect();
      analyserRef.current?.disconnect();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      audioCtxRef.current?.close();
      audioCtxRef.current = null;
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
      mediaStreamRef.current = null;
    } finally {
      onStop();
    }
  }, [onStop]);

  useEffect(() => {
    if (!isActive && processorRef.current) {
      stop();
    }
  }, [isActive, stop]);

  return (
    <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-slate-200">Audio Recorder</h3>
        <span className="text-xs text-slate-400 font-medium">Level: {(level * 100).toFixed(0)}%</span>
      </div>
      <div className="flex items-center gap-4">
        <button
          onClick={() => (isActive ? stop() : start())}
          disabled={disabled}
          aria-label={isActive ? 'Stop recording' : 'Start recording'}
          aria-pressed={isActive}
          className={clsx(
            'inline-flex items-center gap-2 px-4 py-2 rounded-xl border font-semibold shadow-sm transition-all duration-150',
            isActive
              ? 'bg-rose-600 text-white border-rose-700 hover:bg-rose-700'
              : 'bg-sky-600 text-white border-sky-700 hover:bg-sky-700',
            disabled ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'
          )}
        >
          {isActive ? <Pause size={18} /> : <Mic size={18} />}
          {isActive ? 'Stop' : 'Record'}
        </button>
        <div className="flex items-center gap-2 text-slate-400"><Volume2 size={16} /> <span className="text-sm">Use a quiet room for best results.</span></div>
      </div>
      
      <div className="mt-4 h-24 flex items-end justify-center gap-1.5">
        {bars.map((b, i) => (
          <div
            key={i}
            className={clsx(
              'w-2 rounded-full transition-all duration-75',
              getBarColor(b)
            )}
            style={{ 
              height: `${Math.max(4, Math.floor(b * 96))}%`,
              background: `linear-gradient(to top, var(--tw-gradient-stops))`,
            }}
            aria-hidden
          />
        ))}
      </div>
      {error && (
        <p className="mt-3 text-sm text-rose-500 flex items-center gap-2"><AlertTriangle size={16} /> {error}</p>
      )}
      <div className="mt-3 text-xs text-slate-500">
        <p>Tips: Keep the mic 10–15 cm away, avoid plosives (P/B), and speak at a steady pace.</p>
      </div>
    </div>
  );
};

export default AudioRecorder;
