import { User, Session, TrainingPlan, AssessmentResult, TranscriptionResult } from '../types';

const API_BASE = 'http://localhost:8000';

export class VoiceCoachAPI {
  private static instance: VoiceCoachAPI;
  
  static getInstance(): VoiceCoachAPI {
    if (!VoiceCoachAPI.instance) {
      VoiceCoachAPI.instance = new VoiceCoachAPI();
    }
    return VoiceCoachAPI.instance;
  }

  async healthCheck(): Promise<any> {
    const response = await fetch(`${API_BASE}/health`);
    return response.json();
  }

  async createUser(username: string): Promise<{user_id: number, username: string}> {
    const response = await fetch(`${API_BASE}/users/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create user: ${response.statusText}`);
    }
    
    return response.json();
  }

  async getUser(userId: number): Promise<User> {
    const response = await fetch(`${API_BASE}/users/${userId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get user: ${response.statusText}`);
    }
    
    return response.json();
  }

  async createSession(userId: number): Promise<Session> {
    const response = await fetch(`${API_BASE}/sessions/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ user_id: userId }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create session: ${response.statusText}`);
    }
    
    return response.json();
  }

  async createTrainingPlan(userId: number, accuracy: number, weeks: number = 4): Promise<TrainingPlan> {
    const response = await fetch(`${API_BASE}/training-plans/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ user_id: userId, accuracy, weeks }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create training plan: ${response.statusText}`);
    }
    
    return response.json();
  }

  async getTrainingPlan(userId: number): Promise<TrainingPlan> {
    const response = await fetch(`${API_BASE}/training-plans/${userId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get training plan: ${response.statusText}`);
    }
    
    return response.json();
  }

  async transcribeAudio(audioFile: File): Promise<TranscriptionResult> {
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    
    const response = await fetch(`${API_BASE}/audio/transcribe`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Failed to transcribe audio: ${response.statusText}`);
    }
    
    return response.json();
  }

  async assessPronunciation(
    referenceText: string,
    hypothesisText: string,
    audioPath: string
  ): Promise<AssessmentResult> {
    const response = await fetch(`${API_BASE}/audio/assess`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        reference_text: referenceText,
        hypothesis_text: hypothesisText,
        audio_path: audioPath,
      }),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to assess pronunciation: ${response.statusText}`);
    }
    
    return response.json();
  }
}

export const api = VoiceCoachAPI.getInstance();
