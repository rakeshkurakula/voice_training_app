import React, { useState, useEffect } from 'react';
import { User, Session, TrainingPlan, AppState } from './types';
import { api } from './services/api';
import { wsService } from './services/websocket';
import Dashboard from './components/Dashboard';
import SessionControls from './components/SessionControls';
import TrainingPlanView from './components/TrainingPlanView';
import AudioRecorder from './components/AudioRecorder';
import { Mic, MicOff, Wifi, WifiOff } from 'lucide-react';

function App() {
  const [appState, setAppState] = useState<AppState>({
    user: null,
    currentSession: null,
    trainingPlan: null,
    isRecording: false,
    transcription: '',
    assessmentResult: null,
    connectionStatus: 'disconnected'
  });

  // Initialize app
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      // Check API health
      await api.healthCheck();
      console.log('API is healthy');

      // Connect WebSocket
      setAppState(prev => ({ ...prev, connectionStatus: 'connecting' }));
      await wsService.connect();
      
      // Set up WebSocket listeners
      wsService.on('connection', (data) => {
        setAppState(prev => ({ ...prev, connectionStatus: data.status }));
      });

      wsService.on('transcription', (data) => {
        setAppState(prev => ({ ...prev, transcription: data.text }));
      });

      wsService.on('session_status', (data) => {
        console.log('Session status:', data);
      });

      // Create or get default user
      const userResponse = await api.createUser('default_user');
      const user = await api.getUser(userResponse.user_id);
      
      // Get training plan
      const trainingPlan = await api.getTrainingPlan(user.user_id);
      
      setAppState(prev => ({
        ...prev,
        user,
        trainingPlan,
        connectionStatus: 'connected'
      }));

    } catch (error) {
      console.error('Failed to initialize app:', error);
      setAppState(prev => ({ ...prev, connectionStatus: 'error' }));
    }
  };

  const startSession = async () => {
    if (!appState.user) return;

    try {
      const session = await api.createSession(appState.user.user_id);
      setAppState(prev => ({ ...prev, currentSession: session }));
      
      // Notify WebSocket
      wsService.send('session_start', { session_id: session.session_id });
      
    } catch (error) {
      console.error('Failed to start session:', error);
    }
  };

  const endSession = async () => {
    if (!appState.currentSession) return;

    try {
      // Notify WebSocket
      wsService.send('session_end', { session_id: appState.currentSession.session_id });
      
      setAppState(prev => ({
        ...prev,
        currentSession: null,
        isRecording: false,
        transcription: '',
        assessmentResult: null
      }));
      
    } catch (error) {
      console.error('Failed to end session:', error);
    }
  };

  const handleAudioData = async (audioBlob: Blob) => {
    try {
      // Convert blob to file for API
      const audioFile = new File([audioBlob], 'recording.wav', { type: 'audio/wav' });
      
      // Transcribe audio
      const transcriptionResult = await api.transcribeAudio(audioFile);
      setAppState(prev => ({ ...prev, transcription: transcriptionResult.transcript }));
      
      // If we have a current exercise, assess pronunciation
      if (appState.trainingPlan?.week_steps.length) {
        const currentStep = appState.trainingPlan.week_steps[0];
        const assessmentResult = await api.assessPronunciation(
          currentStep.description,
          transcriptionResult.transcript,
          URL.createObjectURL(audioBlob)
        );
        setAppState(prev => ({ ...prev, assessmentResult }));
      }
      
    } catch (error) {
      console.error('Failed to process audio:', error);
    }
  };

  const getConnectionIndicator = () => {
    const { connectionStatus } = appState;
    switch (connectionStatus) {
      case 'connected':
        return <Wifi className="w-5 h-5 text-green-500" />;
      case 'connecting':
        return <Wifi className="w-5 h-5 text-yellow-500 animate-pulse" />;
      case 'disconnected':
      case 'error':
        return <WifiOff className="w-5 h-5 text-red-500" />;
      default:
        return <WifiOff className="w-5 h-5 text-gray-500" />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-2xl font-bold text-gray-900">VoiceCoach 2.0</h1>
              <div className="ml-4 flex items-center space-x-2">
                {getConnectionIndicator()}
                <span className="text-sm text-gray-500">
                  {appState.connectionStatus}
                </span>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {appState.user && (
                <span className="text-sm text-gray-700">
                  Welcome, {appState.user.username || 'User'}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Column - Dashboard */}
          <div className="lg:col-span-2">
            {appState.user ? (
              <Dashboard 
                user={appState.user} 
                assessmentResult={appState.assessmentResult}
              />
            ) : (
              <div className="bg-white rounded-lg shadow p-6">
                <div className="animate-pulse">
                  <div className="h-4 bg-gray-200 rounded w-3/4 mb-4"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                </div>
              </div>
            )}

            {/* Audio Recording Section */}
            <div className="mt-8">
              <AudioRecorder
                isRecording={appState.isRecording}
                onAudioData={handleAudioData}
                onRecordingStateChange={(recording) => 
                  setAppState(prev => ({ ...prev, isRecording: recording }))
                }
              />
            </div>

            {/* Transcription Display */}
            {appState.transcription && (
              <div className="mt-6 bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Live Transcription
                </h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-gray-700">{appState.transcription}</p>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Controls & Training Plan */}
          <div className="space-y-8">
            
            {/* Session Controls */}
            <SessionControls
              currentSession={appState.currentSession}
              isRecording={appState.isRecording}
              onStartSession={startSession}
              onEndSession={endSession}
            />

            {/* Training Plan */}
            {appState.trainingPlan && (
              <TrainingPlanView trainingPlan={appState.trainingPlan} />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
