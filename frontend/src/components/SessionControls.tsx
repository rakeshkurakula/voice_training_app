import React from 'react';
import { Session } from '../types';
import { Play, Square, Mic, MicOff } from 'lucide-react';

interface SessionControlsProps {
  currentSession: Session | null;
  isRecording: boolean;
  onStartSession: () => void;
  onEndSession: () => void;
}

const SessionControls: React.FC<SessionControlsProps> = ({
  currentSession,
  isRecording,
  onStartSession,
  onEndSession
}) => {
  const getStatusIndicator = () => {
    if (!currentSession) {
      return (
        <div className="flex items-center text-gray-500">
          <div className="w-2 h-2 bg-gray-400 rounded-full mr-2"></div>
          Ready to start
        </div>
      );
    }

    if (isRecording) {
      return (
        <div className="flex items-center text-red-500">
          <div className="w-2 h-2 bg-red-500 rounded-full mr-2 animate-pulse"></div>
          <Mic className="w-4 h-4 mr-1" />
          Listening...
        </div>
      );
    }

    return (
      <div className="flex items-center text-blue-500">
        <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
        Session active
      </div>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Session Controls</h3>
      </div>
      <div className="p-6">
        
        {/* Status Indicator */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Status</span>
            {getStatusIndicator()}
          </div>
        </div>

        {/* Control Buttons */}
        <div className="space-y-3">
          {!currentSession ? (
            <button
              onClick={onStartSession}
              className="w-full flex items-center justify-center px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              <Play className="w-5 h-5 mr-2" />
              Start Training Session
            </button>
          ) : (
            <button
              onClick={onEndSession}
              className="w-full flex items-center justify-center px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              <Square className="w-5 h-5 mr-2" />
              End Session
            </button>
          )}
        </div>

        {/* Session Info */}
        {currentSession && (
          <div className="mt-6 p-4 bg-gray-50 rounded-lg">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Current Session</h4>
            <div className="space-y-1 text-sm text-gray-600">
              <div>Session ID: {currentSession.session_id}</div>
              <div>User ID: {currentSession.user_id}</div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-6 p-4 bg-blue-50 rounded-lg">
          <h4 className="text-sm font-medium text-blue-800 mb-2">How to Practice</h4>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>1. Start a training session</li>
            <li>2. Read the training exercises aloud</li>
            <li>3. Get real-time feedback on your pronunciation</li>
            <li>4. Complete exercises to improve your score</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default SessionControls;
