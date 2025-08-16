import React from 'react';
import { User, AssessmentResult } from '../types';
import { TrendingUp, Award, Target, Calendar } from 'lucide-react';

interface DashboardProps {
  user: User;
  assessmentResult?: AssessmentResult | null;
}

const Dashboard: React.FC<DashboardProps> = ({ user, assessmentResult }) => {
  const formatPercentage = (value: number) => `${(value * 100).toFixed(1)}%`;

  const getScoreColor = (score: number) => {
    if (score >= 0.85) return 'text-green-600';
    if (score >= 0.70) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 0.85) return 'bg-green-50 border-green-200';
    if (score >= 0.70) return 'bg-yellow-50 border-yellow-200';
    return 'bg-red-50 border-red-200';
  };

  return (
    <div className="space-y-6">
      {/* Progress Overview */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Progress Dashboard</h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            
            {/* CEFR Level */}
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto bg-blue-100 rounded-lg mb-3">
                <Award className="w-6 h-6 text-blue-600" />
              </div>
              <p className="text-sm text-gray-500">Level</p>
              <p className="text-2xl font-bold text-gray-900">{user.cefr_level}</p>
            </div>

            {/* Latest Score */}
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto bg-green-100 rounded-lg mb-3">
                <Target className="w-6 h-6 text-green-600" />
              </div>
              <p className="text-sm text-gray-500">Latest Score</p>
              <p className={`text-2xl font-bold ${getScoreColor(user.latest_score)}`}>
                {formatPercentage(user.latest_score)}
              </p>
            </div>

            {/* Streak */}
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto bg-orange-100 rounded-lg mb-3">
                <Calendar className="w-6 h-6 text-orange-600" />
              </div>
              <p className="text-sm text-gray-500">Streak</p>
              <p className="text-2xl font-bold text-gray-900">{user.streak} days</p>
            </div>

            {/* Practice Sessions */}
            <div className="text-center">
              <div className="flex items-center justify-center w-12 h-12 mx-auto bg-purple-100 rounded-lg mb-3">
                <TrendingUp className="w-6 h-6 text-purple-600" />
              </div>
              <p className="text-sm text-gray-500">Sessions</p>
              <p className="text-2xl font-bold text-gray-900">{user.history_count}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Current Assessment */}
      {assessmentResult && (
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">Current Assessment</h3>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              
              {/* Phoneme Accuracy */}
              <div className={`p-4 rounded-lg border ${getScoreBgColor(assessmentResult.phoneme_accuracy)}`}>
                <p className="text-sm text-gray-600">Pronunciation</p>
                <p className={`text-xl font-bold ${getScoreColor(assessmentResult.phoneme_accuracy)}`}>
                  {formatPercentage(assessmentResult.phoneme_accuracy)}
                </p>
              </div>

              {/* Word Error Rate */}
              <div className={`p-4 rounded-lg border ${getScoreBgColor(1 - assessmentResult.word_error_rate)}`}>
                <p className="text-sm text-gray-600">Word Accuracy</p>
                <p className={`text-xl font-bold ${getScoreColor(1 - assessmentResult.word_error_rate)}`}>
                  {formatPercentage(1 - assessmentResult.word_error_rate)}
                </p>
              </div>

              {/* Pace */}
              <div className="p-4 rounded-lg border bg-blue-50 border-blue-200">
                <p className="text-sm text-gray-600">Pace</p>
                <p className="text-xl font-bold text-blue-600">
                  {assessmentResult.pace_wpm} WPM
                </p>
              </div>

              {/* CEFR Level */}
              <div className="p-4 rounded-lg border bg-indigo-50 border-indigo-200">
                <p className="text-sm text-gray-600">Level</p>
                <p className="text-xl font-bold text-indigo-600">
                  {assessmentResult.cefr_level}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analytics Charts */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Analytics</h3>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            {/* Accuracy Trend */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Accuracy Trend</h4>
              <div className="h-32 bg-gray-50 rounded-lg flex items-center justify-center">
                {user.analytics.accuracy.length > 0 ? (
                  <div className="text-sm text-gray-500">
                    {user.analytics.accuracy.length} data points
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">No data yet</div>
                )}
              </div>
            </div>

            {/* WER Trend */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Error Rate Trend</h4>
              <div className="h-32 bg-gray-50 rounded-lg flex items-center justify-center">
                {user.analytics.wer.length > 0 ? (
                  <div className="text-sm text-gray-500">
                    {user.analytics.wer.length} data points
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">No data yet</div>
                )}
              </div>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
            {user.analytics.moving_average && (
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-600">7-day Moving Average</p>
                <p className="text-lg font-semibold text-gray-900">
                  {formatPercentage(user.analytics.moving_average)}
                </p>
              </div>
            )}

            {user.analytics.month_over_month && (
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-sm text-gray-600">Month over Month</p>
                <p className={`text-lg font-semibold ${
                  user.analytics.month_over_month > 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {user.analytics.month_over_month > 0 ? '+' : ''}{user.analytics.month_over_month.toFixed(1)}%
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
