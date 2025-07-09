"""Phoneme‑level articulation scoring."""
from __future__ import annotations
from dataclasses import dataclass
import phonemizer, jiwer, librosa, numpy as np

@dataclass
class Scores:
    wer: float
    pace_wpm: float
    phoneme_acc: float

def compute_scores(reference: str, hypothesis: str,
                   wav_path: str) -> Scores:
    # WER
    wer = jiwer.wer(reference, hypothesis)
    # Pace (words per minute)
    speech_dur = librosa.get_duration(path=wav_path)
    pace = len(hypothesis.split()) / (speech_dur / 60.0)
    # Phoneme accuracy
    phon_ref = phonemizer.phonemize(reference, backend="espeak")
    phon_hyp = phonemizer.phonemize(hypothesis, backend="espeak")
    correct = sum(r==h for r,h in zip(phon_ref, phon_hyp))
    phon_acc = correct / max(len(phon_ref),1)
    return Scores(wer, pace, phon_acc)
