# VoiceCoach — Gaps & Missing Pieces Checklist

This complements **“Component Architecture & Best Practices.”** Use it as a quick audit before shipping a local MVP → pilot.

---

## P0 Gaps (ship‑blockers)

* **Secure Recording Matrix**: ensure `getUserMedia` works on Chrome/Edge/Firefox/Safari (desktop/mobile) with fallbacks (`audio/mp4` for Safari). Acceptance: matrix green across target browsers.
* **Audio Normalization Pipeline**: convert to 16 kHz mono, normalize loudness, trim silence (ffmpeg/WebAudio). Acceptance: server receives consistent `webm/mp3/wav` → `wav 16k`.
* **ASR Contract & Timeout**: strict `{text, duration_sec}`; 30s server timeout + retry/backoff; surface partial failures. Acceptance: graceful UI on error with Upload fallback.
* **LLM Guardrails**: JSON schema validate responses (zod), length limits, topic filters, profanity gate. Acceptance: app never crashes from malformed LLM output.
* **Privacy & Deletion**: “Delete my data” action (audio + transcript + metrics). Acceptance: one click purge; log entry recorded.

---

## P1 Gaps (pilot‑ready)

* **Persistence**: sessions in SQLite/Supabase; export CSV. Acceptance: last 30 sessions load <200ms.
* **Telemetry Dashboards**: charts for WPM/fillers distribution, ASR latency p50/p95, LLM cost. Acceptance: Grafana/Metabase reachable locally.
* **CI Pipeline**: lint, typecheck, unit, component, e2e, contract tests; preview deploy. Acceptance: red/green gate before merge.
* **Security Headers**: CSP (script/style/img/connect), HSTS, Referrer‑Policy, Permissions‑Policy (`microphone=(self)`), COOP/COEP. Acceptance: no critical issues in Mozilla Observatory.
* **Error Budget & SLOs**: SLO: ASR success ≥ 99%, p95 latency ≤ 6s (60s clip), client error rate ≤ 1%. Acceptance: weekly burn report.

---

## P2 Enhancements (delight)

* **PWA (Installable)**: offline drills, home‑screen install, background audio. Acceptance: Lighthouse PWA ≥ 90.
* **Prosody v1**: pitch range (CREPE/pyin), energy variance; per‑drill feedback. Acceptance: pitch range reported in semitones.
* **Phoneme‑level Feedback (scripted drills)**: forced alignment (Montreal Forced Aligner/gentle) for consonant/vowel errors. Acceptance: per‑word timings and mispronunciations list.
* **A/B Prompt Experiments**: prompt versioning + randomization; report score deltas. Acceptance: experiment report with power ≥ 0.8.
* **Internationalization**: en‑IN copy pack; local idioms; Hindi/Telegu topic packs. Acceptance: toggle locale without rebuild.

---

## Browser Capability Matrix (target)

| Capability                             | Chrome (Win/Mac/Android) | Edge | Firefox     | Safari (macOS/iOS) |
| -------------------------------------- | ------------------------ | ---- | ----------- | ------------------ |
| `MediaRecorder audio/webm;codecs=opus` | ✅                        | ✅    | ⚠️ (varies) | ❌                  |
| `MediaRecorder audio/mp4;codecs=aac`   | ⚠️                       | ⚠️   | ❌           | ✅                  |
| Mic on `http://localhost`              | ✅                        | ✅    | ✅           | ✅                  |
| Mic on custom `http://`                | ❌                        | ❌    | ❌           | ❌                  |
| Autoplay audio w/o gesture             | ❌                        | ❌    | ❌           | ❌                  |

> Plan: prefer **webm/opus**, fall back to **mp4/aac** on Safari; always run on **localhost/https**.

---

## Audio Processing Pipeline (reference)

```
Client: MediaRecorder → Blob
   ↳ if Safari: audio/mp4 (AAC)
Upload/Record → Backend
ffmpeg steps:
  1) detect format
  2) loudnorm (EBU R128), highpass 80Hz, remove stereo
  3) resample 16kHz mono PCM WAV
→ ASR (faster‑whisper base; vad_filter)
→ metrics (WER for scripted)
→ store session row
```

---

## LLM Safety & Reliability

* **Schema‑First**: zod schemas for `/llm/*` responses; reject/repair on mismatch.
* **Prompt Hygiene**: system guard + explicit JSON instruction; max tokens; stop sequences; profanity/topic filters for public topics.
* **Caching & Cost**: cache by `(skill, topic, cefr, count)`; monthly budget limit; alert at 80%.
* **Adversarial Prompts**: red‑team set for jailbreaks; test in CI.

---

## Security Checklist

* [ ] CSP example:

```
Content-Security-Policy: default-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' http://localhost:8000; script-src 'self'; style-src 'self' 'unsafe-inline'
```

* [ ] Permissions‑Policy: `microphone=(self)`
* [ ] Rate limit: `/asr` ≤ 30 req/min/IP; `/llm/*` ≤ 60 req/min/IP
* [ ] Upload limits: ≤ 30 MB; MIME whitelist; magic‑byte sniff
* [ ] Dependency scan (npm/pip); license audit

---

## Observability (event schema)

```json
{
  "session_id": "uuid",
  "events": [
    {"t":"record.started","ts":1690000000,"meta":{"ua":"..."}},
    {"t":"record.stopped","ts":1690000060,"meta":{"duration":60}},
    {"t":"asr.success","ts":1690000061,"meta":{"ms":2200}},
    {"t":"llm.generate","ts":1690000065,"meta":{"model":"gpt-4o-mini","tokens":450}}
  ]
}
```

---

## Release Discipline

* **Environments**: `dev (localhost) → staging (https) → prod`.
* **Versioning**: `app@x.y.z`, `prompt@rev`, `model@name`. Attach to session rows for reproducibility.
* **Rollbacks**: blue/green or feature flags; keep last 2 backend builds warm.

---

## QA Playbook

* **Happy paths**: record 10s, upload mp3 60s, LLM generate/critique.
* **Edge**: deny mic, unplug mic mid‑record, zero‑length audio, 10‑minute file.
* **Devices**: low‑end Android Chrome, iPhone Safari, Windows Firefox.

---

## Open Questions (please decide)

1. **Mobile first?** If yes, target Safari iOS + Android Chrome with AAC fallback from day‑1.
2. **Data retention**: how long to keep audio/transcripts by default? (7/30/90 days)
3. **ASR path**: local (FastAPI faster‑whisper) vs cloud? latency/cost tradeoff.
4. **PWA**: do we want installable mobile practice this release?
5. **Phoneme feedback**: include MFA now (heavier) or defer to v2?

---

## 7‑Day Punch List (add‑on to your existing plan)

Day 1: Capability matrix test + Safari AAC fallback

Day 2: ffmpeg normalization + 16k resample in backend

Day 3: zod‑validated `/llm/*` responses + cache

Day 4: CSP/headers + rate limits + upload limits

Day 5: SQLite sessions + export CSV + telemetry events

Day 6: Dashboards (p50/p95 ASR, LLM tokens)

Day 7: Playwright e2e on 3 flows + PRR checklist

---

## PRR (Production Readiness Review) Mini‑Template

* **SLOs**: ASR success, latency targets, error budget
* **Backups**: session DB daily, 7‑day retention
* **Incident**: on‑call contact, sev levels, runbook link
* **Risk**: ASR model drift; LLM cost spike; Safari codec mismatch (mitigation listed)

---

If you want, I can fold these into your existing **Local Implementation Plan** as a final consolidated doc.
