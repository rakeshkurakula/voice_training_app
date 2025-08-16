# VoiceCoach 2.0 - UI Planning Guide

## 🏗️ Current Architecture

### **Backend (FastAPI) - Port 8000**
- **Location**: `/backend/main.py`
- **Status**: ✅ Running and healthy
- **API Documentation**: http://localhost:8000/docs

### **Frontend (React + TypeScript) - Port 3000**
- **Location**: `/frontend/src/`
- **Status**: ✅ Running with Vite dev server
- **Framework**: React 18 + TypeScript + Tailwind CSS

---

## 🎨 Current UI Components

### **1. Main Application (`App.tsx`)**
**Location**: `/frontend/src/App.tsx`
**Purpose**: Root component with state management and service integration

**Current Features**:
- ✅ WebSocket connection management
- ✅ User session handling
- ✅ Real-time audio processing
- ✅ Global state management
- ✅ Service initialization

**Layout Structure**:
```
┌─ Header (Connection status, User info)
├─ Main Content Area
│  ├─ Left Column (2/3 width)
│  │  ├─ Dashboard Component
│  │  ├─ Audio Recorder Component
│  │  └─ Live Transcription Display
│  └─ Right Column (1/3 width)
│     ├─ Session Controls
│     └─ Training Plan View
└─ Footer (Optional)
```

---

### **2. Dashboard Component (`Dashboard.tsx`)**
**Location**: `/frontend/src/components/Dashboard.tsx`
**Purpose**: Main progress and analytics display

**Current Sections**:
1. **Progress Overview** (4-column grid):
   - CEFR Level (Award icon)
   - Latest Score (Target icon)
   - Streak Days (Calendar icon)
   - Practice Sessions (TrendingUp icon)

2. **Current Assessment** (if active):
   - Pronunciation accuracy
   - Word accuracy
   - Speaking pace (WPM)
   - CEFR level

3. **Analytics Charts**:
   - Accuracy trend (placeholder)
   - Error rate trend (placeholder)
   - 7-day moving average
   - Month-over-month change

**Color Coding**:
- 🟢 Green: Scores ≥85%
- 🟡 Yellow: Scores 70-84%
- 🔴 Red: Scores <70%

---

### **3. Session Controls (`SessionControls.tsx`)**
**Location**: `/frontend/src/components/SessionControls.tsx`
**Purpose**: Training session management

**Features**:
- ✅ Start/End session buttons
- ✅ Real-time status indicator
- ✅ Session information display
- ✅ Practice instructions

**States**:
1. **Ready**: Gray dot + "Ready to start"
2. **Active**: Blue dot + "Session active"
3. **Recording**: Red dot + pulsing + "Listening..."

---

### **4. Audio Recorder (`AudioRecorder.tsx`)**
**Location**: `/frontend/src/components/AudioRecorder.tsx`
**Purpose**: Real-time audio capture and visualization

**Features**:
- ✅ WebRTC audio capture
- ✅ Real-time audio visualization (20 bars)
- ✅ Volume level monitoring
- ✅ Recording controls
- ✅ Error handling for microphone permissions

**Visual Elements**:
- 🎤 Large microphone button (blue/red states)
- 📊 Audio level bars
- 📈 Volume percentage indicator
- 💡 Recording tips section

---

### **5. Training Plan View (`TrainingPlanView.tsx`)**
**Location**: `/frontend/src/components/TrainingPlanView.tsx`
**Purpose**: Interactive training exercises

**Features**:
- ✅ Week-based exercise organization
- ✅ Progress tracking with completion checkboxes
- ✅ Text-to-speech playback for exercises
- ✅ Difficulty and focus area tags
- ✅ Week navigation

**Exercise Structure**:
```
Step N [Checkbox] [Difficulty Badge] [Focus Area Badge]
Description text...
[▶ Play Reference Audio] button
```

---

## 🔧 Technical Integration

### **API Endpoints Available**
```
GET  /health                    - Service health check
POST /users/                    - Create user
GET  /users/{id}               - Get user data + analytics
POST /sessions/                - Create training session
GET  /training-plans/{user_id} - Get training plan
POST /audio/transcribe         - Upload & transcribe audio
POST /audio/assess            - Pronunciation assessment
WS   /ws                      - Real-time communication
```

### **WebSocket Message Types**
```typescript
// Outbound (Frontend → Backend)
{ type: "session_start", data: {...} }
{ type: "session_end", data: {...} }
{ type: "audio_chunk", data: {...} }

// Inbound (Backend → Frontend)
{ type: "transcription", data: { text, confidence } }
{ type: "session_status", data: { status, message } }
```

### **State Management**
```typescript
interface AppState {
  user: User | null
  currentSession: Session | null
  trainingPlan: TrainingPlan | null
  isRecording: boolean
  transcription: string
  assessmentResult: AssessmentResult | null
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
}
```

---

## 🎯 UI Planning Opportunities

### **1. Design System Enhancement**
**Current**: Basic Tailwind CSS classes
**Opportunity**: 
- Create design tokens (colors, spacing, typography)
- Build reusable component library
- Implement consistent theming

### **2. Data Visualization**
**Current**: Placeholder chart areas
**Opportunity**:
- Integrate Chart.js or Recharts
- Real-time progress graphs
- Interactive analytics dashboard

### **3. User Experience Flow**
**Current**: Basic session start/stop
**Opportunity**:
- Onboarding wizard
- Tutorial tooltips
- Progressive disclosure of features

### **4. Responsive Design**
**Current**: Desktop-focused layout
**Opportunity**:
- Mobile-first responsive design
- Touch-friendly controls
- Adaptive layouts

### **5. Audio Experience**
**Current**: Basic recorder
**Opportunity**:
- Waveform visualization
- Audio playback controls
- Recording quality feedback

---

## 📱 Recommended UI Improvements

### **Priority 1: Essential UX**
1. **Loading States**: Add skeletons and spinners
2. **Error Boundaries**: Graceful error handling
3. **Feedback Systems**: Toast notifications
4. **Accessibility**: ARIA labels, keyboard navigation

### **Priority 2: Enhanced Features**
1. **Audio Visualizations**: Real waveforms, spectrograms
2. **Progress Analytics**: Interactive charts
3. **Exercise Variations**: Multiple practice modes
4. **Achievement System**: Badges, streaks, goals

### **Priority 3: Advanced Features**
1. **AI Coaching**: Smart recommendations
2. **Social Features**: Sharing progress
3. **Customization**: Themes, preferences
4. **Export/Import**: Progress data management

---

## 🚀 Getting Started with UI Development

### **1. Development Setup**
```bash
# Start both services
cd /Users/rakeshk94/Desktop/voice_training_app
./setup.sh

# Or manually:
# Backend: cd backend && python main.py
# Frontend: cd frontend && npm run dev
```

### **2. Access Points**
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### **3. Component Development**
```bash
# Add new components in:
frontend/src/components/

# Available UI libraries:
- Tailwind CSS (styling)
- Lucide React (icons)
- TypeScript (type safety)
```

### **4. Testing Audio Features**
- Grant microphone permissions in browser
- Use Chrome/Edge for best WebRTC support
- Test with different audio inputs/quality

---

## 📊 Current Metrics & Data Flow

### **User Progress Tracking**
- ✅ CEFR levels (A1, A2, B1, B2, C1, C2)
- ✅ Phoneme accuracy percentage
- ✅ Word Error Rate (WER)
- ✅ Speaking pace (WPM)
- ✅ Daily practice streaks

### **Real-time Processing**
1. **Audio Capture**: WebRTC → Blob
2. **Transcription**: Blob → Whisper → Text
3. **Assessment**: Reference + Hypothesis → Scores
4. **Feedback**: Scores → UI Updates

### **Data Persistence**
- SQLite database for user progress
- Session-based training plans
- Historical analytics data

---

This README provides a complete overview of the current VoiceCoach 2.0 UI structure and architecture. Use this as your foundation for planning UI improvements, new features, and design enhancements!
