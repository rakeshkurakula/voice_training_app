// Recorder adapter (browser) — per components.md best practices
// Responsibility: isolate getUserMedia quirks from UI; provide a stable Recorder interface

import { useEffect, useRef, useState } from 'react';

export type RecorderStatus =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'denied'
  | 'unsupported'
  | 'error'
  | 'uploading';

export interface Recorder {
  status: RecorderStatus;
  duration: number;
  audioUrl?: string;
  error?: string;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
  setFromFile: (file: File) => void;
}

function isSecure(): boolean {
  if (typeof window === 'undefined') return false;
  // @ts-expect-error web
  if (window.isSecureContext) return true;
  return (
    typeof location !== 'undefined' &&
    (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')
  );
}

/**
 * useRecorderBrowser — MediaRecorder-based adapter with robust guards
 * Guards:
 *  - Secure context or localhost
 *  - Feature detect navigator.mediaDevices.getUserMedia
 *  - Request only on user gesture (start is called from a click)
 *  - Best-effort Permissions API preflight
 *  - Cleanup: stop tracks on stop/unmount; clear timers
 *  - Timeouts: treat long requesting as error
 */
export function useRecorderBrowser(): Recorder {
  const [status, setStatus] = useState<RecorderStatus>('idle');
  const [duration, setDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState<string>();
  const [error, setError] = useState<string>();
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<number>();
  const reqTimeout = useRef<number>();

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      try {
        mediaRef.current?.stream.getTracks().forEach((t) => t.stop());
      } catch {}
      if (timer.current) window.clearInterval(timer.current);
      if (reqTimeout.current) window.clearTimeout(reqTimeout.current);
    };
  }, []);

  // Preflight support + secure context checks once
  useEffect(() => {
    const hasMedia = !!(typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia);
    if (!hasMedia) {
      setStatus('unsupported');
      setError('Microphone not supported in this browser.');
      return;
    }
    if (!isSecure()) {
      setStatus('unsupported');
      setError('Microphone requires HTTPS or localhost.');
      return;
    }
    // Best-effort permissions preflight (non-blocking)
    try {
      // @ts-expect-error Permissions API typing
      navigator.permissions?.query?.({ name: 'microphone' as any }).then((res: any) => {
        if (res?.state === 'denied') {
          setStatus('denied');
          setError('Microphone permission denied. Enable it in the address bar and reload.');
        }
      });
    } catch {}
  }, []);

  async function start() {
    if (status === 'unsupported') return;
    setError(undefined);
    setStatus('requesting');
    // Timeout safety for stuck requests
    reqTimeout.current = window.setTimeout(() => {
      if (status === 'requesting') {
        setStatus('error');
        setError('Timed out requesting microphone. Try again or use Upload.');
      }
    }, 10000);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      window.clearTimeout(reqTimeout.current);
      const mr = new MediaRecorder(stream);
      mediaRef.current = mr;
      chunks.current = [];
      setDuration(0);

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      mr.onstop = () => {
        try {
          const blob = new Blob(chunks.current, { type: 'audio/webm' });
          setAudioUrl(URL.createObjectURL(blob));
        } catch {}
        try {
          stream.getTracks().forEach((t) => t.stop());
        } catch {}
        if (timer.current) window.clearInterval(timer.current);
      };

      mr.start(100);
      setStatus('recording');
      timer.current = window.setInterval(() => setDuration((d) => d + 1), 1000);
    } catch (e: any) {
      window.clearTimeout(reqTimeout.current);
      if (e?.name === 'NotAllowedError' || e?.name === 'PermissionDeniedError') {
        setStatus('denied');
        setError('Permission denied. Allow mic in the address bar and reload.');
      } else if (e?.name === 'NotFoundError') {
        setStatus('error');
        setError('No microphone found. Connect one or use Upload.');
      } else {
        setStatus('error');
        setError('Could not start recording. Use Upload as a fallback.');
      }
    }
  }

  function stop() {
    try {
      mediaRef.current?.stop();
    } catch {}
    setStatus('idle');
  }

  function reset() {
    if (audioUrl) {
      try { URL.revokeObjectURL(audioUrl); } catch {}
    }
    setAudioUrl(undefined);
    setDuration(0);
    setStatus('idle');
    setError(undefined);
  }

  function setFromFile(file: File) {
    try {
      const url = URL.createObjectURL(file);
      setAudioUrl(url);
      setStatus('uploading');
      setError(undefined);
    } catch (e: any) {
      setStatus('error');
      setError('Failed to load file.');
    }
  }

  return { status, duration, audioUrl, error, start, stop, reset, setFromFile } as Recorder;
}
