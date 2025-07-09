"""Personalized plan generator based on assessment metrics."""
from __future__ import annotations
import datetime as dt

def accuracy_to_cefr(phoneme_acc: float) -> str:
    if phoneme_acc < 0.6:
        return "A1"
    elif phoneme_acc < 0.75:
        return "B1"
    elif phoneme_acc < 0.85:
        return "B2"
    elif phoneme_acc < 0.93:
        return "C1"
    else:
        return "C2"

def generate_plan(phoneme_acc: float, weeks: int = 4) -> dict:
    level = accuracy_to_cefr(phoneme_acc)
    plan = {"level": level, "weeks": weeks, "start_date": dt.date.today().isoformat(), "steps": []}
    # Example step templates
    step_templates = {
        "A1": ["Daily basic articulation drills (plosives, vowels)", "Repeat after TTS", "Record and listen"],
        "B1": ["Intermediate drills (fricatives, blends)", "Pacing exercises", "Shadowing practice"],
        "B2": ["Advanced drills (diphthongs, prosody)", "Tongue twisters", "Expressiveness"],
        "C1": ["Conversational practice", "Expressive reading", "Self-evaluation"],
        "C2": ["Performance-level practice", "Accent refinement", "Peer feedback"]
    }
    steps = step_templates.get(level, step_templates["A1"])
    for week in range(weeks):
        for i, desc in enumerate(steps):
            plan["steps"].append({
                "week": week + 1,
                "step_num": i + 1,
                "description": desc,
                "completed": False
            })
    return plan
