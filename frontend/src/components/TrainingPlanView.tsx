import React from 'react';
import { ChevronLeft, ChevronRight, Play } from 'lucide-react';
import {
  TrainingPlan,
  TrainingWeek,
  TrainingExercise,
} from "../types";
import { clsx } from '../utils';

// TODO: Move Skeleton to its own component and import it
function Skeleton({ title, lines = 3 }: { title?: string; lines?: number }) {
  return (
    <div className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      {title && <div className="h-5 w-40 mb-4 bg-slate-700/50 rounded animate-pulse" />}
      <div className="space-y-3">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-4 bg-slate-700/50 rounded animate-pulse" style={{ width: `${100 - i * 10}%` }} />
        ))}
      </div>
    </div>
  );
}

interface TrainingPlanViewProps {
  plan: TrainingPlan | null;
  currentWeek: number;
  onPrev: () => void;
  onNext: () => void;
  onToggle: (week: number, id: string) => void;
  onPlay: (text: string) => void;
  activeExerciseId: string | null;
  onSetActive: (id: string) => void;
}

const TrainingPlanView: React.FC<TrainingPlanViewProps> = ({
  plan,
  currentWeek,
  onPrev,
  onNext,
  onToggle,
  onPlay,
  activeExerciseId,
  onSetActive,
}) => {
  if (!plan) return <Skeleton title="Training Plan" lines={5} />;

  const week = plan.weeks.find((w) => w.weekNumber === currentWeek) ?? plan.weeks[0];
  const completedCount = week.exercises.filter((ex) => ex.completed).length;
  const totalCount = week.exercises.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  return (
    <section className="rounded-2xl border border-slate-800/50 p-4 bg-slate-800/60 shadow-lg ring-1 ring-inset ring-slate-700/50">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-200">
          Training Plan – Week {week.weekNumber}
        </h3>
        <div className="flex items-center gap-2">
          <button
            aria-label="Previous week"
            onClick={onPrev}
            className="p-2 rounded-lg border border-slate-700 hover:bg-slate-700/50 transition-all"
          >
            <ChevronLeft size={18} />
          </button>
          <button
            aria-label="Next week"
            onClick={onNext}
            className="p-2 rounded-lg border border-slate-700 hover:bg-slate-700/50 transition-all"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-1 text-xs font-medium text-slate-400">
          <span>Weekly Progress</span>
          <span>
            {completedCount} / {totalCount} Done
          </span>
        </div>
        <div className="w-full bg-slate-700/50 rounded-full h-2.5">
          <div
            className="bg-gradient-to-r from-sky-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="space-y-3">
        {week.exercises.map((ex) => (
          <div
            key={ex.id}
            className={clsx(
              "rounded-xl border p-3 transition-all duration-200 cursor-pointer",
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
                  onChange={(e) => {
                    e.stopPropagation(); // Prevent onClick from firing on the parent div
                    onToggle(week.weekNumber, ex.id);
                  }}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-700 text-sky-500 focus:ring-sky-500 focus:ring-offset-slate-800"
                />
                <label htmlFor={`ex-${ex.id}`} className="font-medium text-slate-200">Step {ex.id}</label>
                <span className="text-xs px-2 py-0.5 rounded-full border border-slate-700 bg-slate-900/60 font-medium">{ex.difficulty}</span>
                <span className="text-xs px-2 py-0.5 rounded-full border border-slate-700 bg-slate-900/60 font-medium">{ex.focus}</span>
              </div>
              <button 
                onClick={(e) => {
                  e.stopPropagation(); // Prevent onClick from firing on the parent div
                  onPlay(ex.referenceText ?? ex.description);
                }}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 border border-indigo-700 transition-all duration-150 hover:scale-105 active:scale-95 text-sm"
              >
                <Play size={14} className="inline mr-1.5 -mt-0.5" /> Play Reference
              </button>
            </div>
            <p className="mt-2 text-sm text-slate-300 pl-7">{ex.description}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default TrainingPlanView;
