import { useState, useEffect, useRef } from "react";
import {
  Shield,
  ChevronDown,
  ArrowRight,
  User,
  Mail,
  Briefcase,
  Upload,
  Mic,
  StopCircle,
  RotateCcw,
  Send,
  CheckCircle2,
  Headphones,
  Loader2,
  Camera,
  CameraOff,
} from "lucide-react";
import Results from './Results';

const API_BASE_URL = `${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api`;
const TOTAL_QUESTIONS = 9;

export default function VoxHireApp() {
  const [showInterview, setShowInterview] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [resultsSessionId, setResultsSessionId] = useState("");
  const [userDetails, setUserDetails] = useState({
    name: "",
    email: "",
    photo: null as string | null,
    role: "frontend",
  });
  const [sessionId, setSessionId] = useState("");

  const startNewSession = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/start`);
      const data = await response.json();
      if (!data.session_id) throw new Error("No session_id in response");
      setSessionId(data.session_id);
      setShowInterview(true);
    } catch (error) {
      console.error("Failed to start session:", error);
      // Use a less intrusive error message
      console.error(`Failed to connect to backend. Make sure the server is running at ${API_BASE_URL}`);
    }
  };

  if (showInterview) {
    return (
      <InterviewPage
        name={userDetails.name}
        email={userDetails.email}
        photo={userDetails.photo}
        role={userDetails.role}
        sessionId={sessionId}
        onBack={() => {
          setShowInterview(false);
          setSessionId("");
        }}
        onFinishInterview={(finalSessionId) => {
          setShowInterview(false);
          setResultsSessionId(finalSessionId);
          setShowResults(true);
        }}
      />
    );
  }

  if (showResults) {
    return (
      <Results
        sessionId={resultsSessionId}
        onBack={() => setShowResults(false)}
        name={userDetails.name}
        email={userDetails.email}
        photo={userDetails.photo}
        role={userDetails.role}
        totalQuestions={TOTAL_QUESTIONS}
      />
    );
  }

  return (
    <SetupPage
      userDetails={userDetails}
      setUserDetails={setUserDetails}
      onStart={startNewSession}
    />
  );
}

// --- SetupPage (No changes) ---
function SetupPage({
  userDetails,
  setUserDetails,
  onStart,
}: {
  userDetails: { name: string; email: string; photo: string | null; role: string };
  setUserDetails: (details: any) => void;
  onStart: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setUserDetails({ ...userDetails, photo: reader.result as string });
      };
      reader.readAsDataURL(file);
    }
  };

  const showCustomAlert = (message: string) => {

    console.warn("Validation Error:", message);
    
    alert(message); // Re-adding alert as per original code, but modal is preferred
  };

  const handleStartInterview = () => {
    if (!userDetails.name.trim()) {
      showCustomAlert("Please enter your name");
      return;
    }
    if (!userDetails.email.trim()) {
      showCustomAlert("Please enter your email");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(userDetails.email)) {
      showCustomAlert("Please enter a valid email address");
      return;
    }
    onStart();
  };

  const roleLabel = userDetails.role.charAt(0).toUpperCase() + userDetails.role.slice(1).replace(/([A-Z])/g, " $1");

  return (
    <div className="min-h-screen bg-neutral-950 text-white font-sans">
      <header className="sticky top-0 z-20 backdrop-blur bg-neutral-950/90 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 grid place-items-center rounded-md bg-white text-neutral-900 font-semibold">VH</div>
            <div className="flex flex-col">
              <span className="text-lg font-semibold">VoxHire</span>
              <span className="text-xs text-neutral-400">Voice-first interview</span>
            </div>
          </div>
          <nav className="hidden sm:flex items-center gap-6 text-sm">
            <button className="text-neutral-300 hover:text-white transition-colors">Privacy</button>
            <button className="text-neutral-300 hover:text-white transition-colors">Help</button>
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl md:text-5xl font-bold mb-4">Start Your Interview</h1>
          <p className="text-lg text-neutral-400">Complete your details and select your role to begin</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <section className="rounded-xl border border-white/10 bg-white/5">
            <div className="p-5 border-b border-white/10">
              <h2 className="text-xl font-semibold">Your Details</h2>
              <p className="text-sm text-neutral-400 mt-1">Tell us about yourself</p>
            </div>
            <div className="p-5 space-y-5">
              <div>
                <label className="block text-sm text-neutral-300 mb-2">Profile Photo (Optional)</label>
                <div className="flex items-center gap-4">
                  <div className="h-20 w-20 rounded-full border-2 border-white/10 bg-neutral-900/60 overflow-hidden flex items-center justify-center">
                    {userDetails.photo ? (
                      <img src={userDetails.photo} alt="Profile" className="h-full w-full object-cover" />
                    ) : (
                      <User className="h-8 w-8 text-neutral-500" />
                    )}
                  </div>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="cursor-pointer inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 transition-colors"
                  >
                    <Upload className="h-4 w-4" />
                    <span className="text-sm">Upload Photo</span>
                    <input type="file" accept="image/*" onChange={handlePhotoUpload} ref={fileInputRef} className="hidden" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm text-neutral-300 mb-2">Full Name *</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                  <input
                    type="text"
                    value={userDetails.name}
                    onChange={(e) => setUserDetails({ ...userDetails, name: e.target.value })}
                    placeholder="Enter your full name"
                    className="w-full bg-neutral-900/60 border border-white/10 rounded-lg text-sm pl-10 pr-3 py-2.5 text-white placeholder:text-neutral-500 outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-neutral-300 mb-2">Email Address *</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
                  <input
                    type="email"
                    value={userDetails.email}
                    onChange={(e) => setUserDetails({ ...userDetails, email: e.target.value })}
                    placeholder="you@example.com"
                    className="w-full bg-neutral-900/60 border border-white/10 rounded-lg text-sm pl-10 pr-3 py-2.5 text-white placeholder:text-neutral-500 outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-white/10 bg-white/5">
            <div className="p-5 border-b border-white/10">
              <h2 className="text-xl font-semibold">Choose Role</h2>
              <p className="text-sm text-neutral-400 mt-1">Select the position you're applying for</p>
            </div>
            <div className="p-5 space-y-5">
              <div>
                <label className="block text-sm text-neutral-300 mb-2">Job Role *</label>
                <div className="relative">
                  <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 z-10" />
                  <select
                    value={userDetails.role}
                    onChange={(e) => setUserDetails({ ...userDetails, role: e.target.value })}
                    className="w-full appearance-none bg-neutral-900/60 border border-white/10 rounded-lg text-sm pl-10 pr-10 py-2.5 text-white outline-none focus:border-indigo-500/50 focus:ring-2 focus:ring-indigo-500/20"
                  >
                    <option value="frontend">Front-End Developer</option>
                    <option value="datascience">Data Scientist</option>
                    <option value="data_analytics">Data Analytics</option>
                    <option value="product">Product Manager</option>
                    <option value="devops">DevOps Engineer</option>
                    <option value="hr">HR / Managerial</option>

                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
                </div>
              </div>

              <div className="rounded-lg border border-white/10 bg-neutral-900/40 p-4">
                <h3 className="text-sm font-semibold mb-2">{roleLabel}</h3>
                <p className="text-xs text-neutral-400">
                  You'll answer AI-generated questions tailored to your role through voice recordings.
                </p>
              </div>

              <div className="flex items-start gap-3 p-3 rounded-lg border border-white/10 bg-white/5">
                <Shield className="h-4 w-4 text-neutral-400 mt-0.5 flex-shrink-0" />
                <p className="text-xs text-neutral-400">
                  Your responses are saved to the backend. Speech is transcribed and sent as text.
                </p>
              </div>
            </div>
          </section>
        </div>

        <div className="mt-8 flex justify-center">
          <button
            onClick={handleStartInterview}
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors shadow-lg shadow-indigo-500/20"
          >
            <span>Start Interview</span>
            <ArrowRight className="h-5 w-5" />
          </button>
        </div>

      </main>

      <footer className="max-w-7xl mx-auto px-6 py-8 border-t border-white/10 text-sm text-neutral-500">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p>© {new Date().getFullYear()} VoxHire. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <button className="hover:text-neutral-300 transition-colors">Terms</button>
            <button className="hover:text-neutral-300 transition-colors">Contact</button>
          </div>
        </div>
      </footer>
    </div>
  );
}

function InterviewPage({
  name,
  email,
  photo,
  role,
  sessionId,
  onBack,
  onFinishInterview
}: {
  name: string;
  email: string;
  photo: string | null;
  role: string;
  sessionId: string;
  onBack: () => void;
  onFinishInterview: (sessionId: string) => void;
}) {
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [statusText, setStatusText] = useState("Ready");
  const [totalSeconds, setTotalSeconds] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);
  const [questionCount, setQuestionCount] = useState(0); 

  const recognitionRef = useRef<any>(null);
  const intervalIdRef = useRef<number | null>(null);
  const isRecordingRef = useRef(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);

  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1).replace(/([A-Z])/g, " $1");

 
  const showCustomAlert = (message: string) => {
    console.warn("Alert:", message);
 
    alert(message); 
  };

  // Initialize camera + microphone for proctoring (single combined permission prompt)
  useEffect(() => {
    let stream: MediaStream | null = null;

    if (!window.isSecureContext) {
      setCameraError("Camera/microphone need a secure (HTTPS) connection. Open the site over https://");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError("Your browser does not support camera/microphone access. Please use Chrome or Edge.");
      return;
    }

    navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      .then((s) => {
        stream = s;
        // Keep video tracks on the visible stream, immediately stop audio tracks
        // so the SpeechRecognition API can take over the mic cleanly.
        s.getAudioTracks().forEach((t) => t.stop());
        const videoOnly = new MediaStream(s.getVideoTracks());
        setCameraStream(videoOnly);
        if (videoRef.current) {
          videoRef.current.srcObject = videoOnly;
        }
      })
      .catch((err: any) => {
        const name = err?.name || "";
        if (name === "NotAllowedError" || name === "PermissionDeniedError") {
          setCameraError("Permission denied. Click the camera icon in the address bar and allow camera + microphone, then refresh.");
        } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
          setCameraError("No camera or microphone detected. Please connect a device and refresh.");
        } else if (name === "NotReadableError" || name === "TrackStartError") {
          setCameraError("Camera or microphone is in use by another app. Close it and refresh.");
        } else {
          setCameraError("Failed to access camera/microphone for monitoring.");
        }
      });
    return () => {
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // Attach stream to video element once both are ready
  useEffect(() => {
    if (videoRef.current && cameraStream) {
      videoRef.current.srcObject = cameraStream;
    }
  }, [cameraStream]);

  const buildRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: any) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalTranscript += event.results[i][0].transcript + ' ';
        }
      }
      setTranscript((prev) => prev + finalTranscript);
    };

    recognition.onaudiostart = () => {
      setStatusText("Microphone ready — speak now");
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      setStatusText(event.error === 'no-speech' ? 'No speech detected. Try again.' : `Error: ${event.error}`);
      isRecordingRef.current = false;
      setIsRecording(false);
      if (intervalIdRef.current) { clearInterval(intervalIdRef.current); intervalIdRef.current = null; }
    };

    recognition.onend = () => {
      if (isRecordingRef.current) {
        isRecordingRef.current = false;
        setIsRecording(false);
        setStatusText('Recording stopped');
      }
    };

    return recognition;
  };

  // Set first question and clean up on unmount
  useEffect(() => {
    getFirstQuestion();
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (_) {}
      }
      if (intervalIdRef.current) clearInterval(intervalIdRef.current);
    };
  }, []);

  const getFirstQuestion = () => {
    setCurrentQuestion("Introduce yourself.");
  };

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60).toString().padStart(2, "0");
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const startRecording = async () => {
    if (!window.isSecureContext) {
      showCustomAlert("Recording requires a secure (HTTPS) connection. Please open this site over https://");
      return;
    }

    // Ensure microphone permission is granted explicitly before SpeechRecognition starts.
    if (navigator.mediaDevices?.getUserMedia) {
      try {
        const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
        probe.getTracks().forEach((t) => t.stop());
      } catch (err: any) {
        const name = err?.name || "";
        if (name === "NotAllowedError" || name === "PermissionDeniedError") {
          showCustomAlert("Microphone permission was denied. Click the lock icon in the address bar, allow microphone access, and refresh.");
        } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
          showCustomAlert("No microphone detected. Please connect one and try again.");
        } else if (name === "NotReadableError" || name === "TrackStartError") {
          showCustomAlert("Microphone is being used by another app. Close it and try again.");
        } else {
          showCustomAlert("Could not access the microphone. Please check your browser permissions.");
        }
        return;
      }
    }

    // Abort any existing session before creating a fresh one
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (_) {}
      recognitionRef.current = null;
    }

    const recognition = buildRecognition();
    if (!recognition) {
      showCustomAlert("Speech recognition not supported in this browser. Please use Chrome or Edge.");
      return;
    }
    recognitionRef.current = recognition;

    setTranscript("");
    setTotalSeconds(0);
    isRecordingRef.current = true;
    setIsRecording(true);
    setStatusText("Preparing microphone...");
    setSubmitted(false);

    const tryStart = (attempt = 0) => {
      try {
        recognition.start();
        intervalIdRef.current = window.setInterval(() => {
          setTotalSeconds((prev) => prev + 1);
        }, 1000);
      } catch (error: any) {
        // InvalidStateError happens if a previous instance is still tearing down.
        // Retry once after a short delay before giving up.
        if (attempt === 0 && error?.name === "InvalidStateError") {
          setTimeout(() => tryStart(1), 250);
          return;
        }
        console.error('Failed to start recording:', error);
        isRecordingRef.current = false;
        setIsRecording(false);
        setStatusText("Failed to start — please refresh and try again.");
      }
    };
    tryStart();
  };

  const stopRecording = () => {
    if (intervalIdRef.current) {
      clearInterval(intervalIdRef.current);
      intervalIdRef.current = null;
    }
    
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (error) {
        console.error('Error stopping recognition:', error);
      }
    }
    
    isRecordingRef.current = false;
    setIsRecording(false);
    setStatusText("Recording stopped");
  };

  const retake = () => {
    setTranscript("");
    setTotalSeconds(0);
    setStatusText("Ready to record");
    setSubmitted(false);
  };

  const submitAnswer = async () => {
    if (!transcript.trim()) {
      showCustomAlert("Please record an answer before submitting.");
      return;
    }

    setIsProcessing(true);
    setSubmitted(true); // Lock submit button
    setStatusText("Submitting...");

    try {
      // Save the current Q&A
      await fetch(`${API_BASE_URL}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: currentQuestion,
          answer: transcript,
          session_id: sessionId,
          name: name,
          email: email,
          role: role
        })
      });

      // --- MODIFIED: Increment question count and check limit ---
      const newQuestionCount = questionCount + 1;
      setQuestionCount(newQuestionCount);

      // Check if this was the last question
      if (newQuestionCount >= TOTAL_QUESTIONS) {
        setInterviewComplete(true);
        setStatusText("Interview complete!");
        setIsProcessing(false); // Stop processing
        return; // Stop here, don't fetch another question
      }
      // --- End Modification ---

      // Get next question
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: transcript,
          domain: role 
        })
      });

      const data = await response.json();

      setCurrentQuestion(data.question);
      setTranscript("");
      setTotalSeconds(0);
      setSubmitted(false);
      isRecordingRef.current = false;
      setIsRecording(false);
      setStatusText("Ready to record");

      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (_) {}
      }
    } catch (error) {
      console.error('Failed to submit answer:', error);
      showCustomAlert('Failed to submit answer. Please try again.');
      setStatusText("Error submitting");
      setSubmitted(false); // Allow resubmission on error
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-white font-sans">
      {/* Proctoring Monitor — fixed top-right, below header, never overlaps submit button */}
      <div className="fixed top-20 right-4 z-10 w-[200px] bg-neutral-900 border border-white/10 rounded-lg overflow-hidden shadow-xl">
        <div className="bg-neutral-800 px-3 py-2 flex items-center gap-2 border-b border-white/10">
          <Camera className="h-3.5 w-3.5 text-neutral-400" />
          <span className="text-xs text-neutral-300">Proctoring Monitor</span>
        </div>
        <div className="relative bg-black" style={{ height: 150 }}>
          {cameraError ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 px-2">
              <CameraOff className="h-8 w-8 text-red-500/60" />
              <span className="text-xs text-red-400 text-center">Camera unavailable</span>
            </div>
          ) : (
            <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          )}
        </div>
        {cameraError && (
          <div className="px-3 py-2 bg-red-500/10 border-t border-red-500/20">
            <p className="text-xs text-red-400">{cameraError}</p>
          </div>
        )}
      </div>

      <header className="sticky top-0 z-20 backdrop-blur bg-neutral-950/90 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 grid place-items-center rounded-md bg-white text-neutral-900 font-semibold">VH</div>
            <div className="flex flex-col">
              <span className="text-lg font-semibold">VoxHire</span>
              <span className="text-xs text-neutral-400">Voice-first interview</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-3">
              {photo && <img src={photo} alt={name} className="h-8 w-8 rounded-full object-cover border border-white/10" />}
              <div className="text-right">
                <p className="text-sm font-medium">{name}</p>
                <p className="text-xs text-neutral-400">{email}</p>
              </div>
            </div>
            <button onClick={onBack} className="text-sm text-neutral-300 hover:text-white transition-colors">Exit</button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div className="rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-md bg-indigo-600/20 border border-indigo-500/30 grid place-items-center">
                <Mic className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <p className="text-sm text-neutral-300">{roleLabel}</p>
                <h2 className="text-lg font-semibold">AI Interview Session</h2>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-neutral-400">{formatTime(totalSeconds)}</p>
              <p className="text-xs text-neutral-500">Session: {sessionId.slice(0, 8)}...</p>
            </div>
          </div>
        </div>

        {isProcessing && !currentQuestion && !interviewComplete ? (
          <div className="rounded-xl border border-white/10 bg-white/5 p-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-indigo-400" />
            <p className="text-neutral-400">Preparing your interview...</p>
          </div>
        ) : (
          <>
            {/* --- MODIFIED: Hide question block when complete --- */}
            {!interviewComplete && (
              <div className="rounded-xl border border-white/10 bg-white/5 overflow-hidden">
                <div className="p-5 border-b border-white/10">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2.5 py-1 rounded-full text-xs border border-white/10 bg-white/5">
                      Question {questionCount + 1} / {TOTAL_QUESTIONS}
                    </span>
                    <span className="text-xs text-neutral-500">Voice answer</span>
                  </div>
                  <h3 className="text-xl md:text-2xl font-semibold">{currentQuestion}</h3>
                </div>

                <div className="p-5 space-y-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <button
                      onClick={startRecording}
                      disabled={isRecording || submitted || isProcessing}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <Mic className="h-4 w-4" />
                      <span className="text-sm font-medium">Start Recording</span>
                    </button>
                    <button
                      onClick={stopRecording}
                      disabled={!isRecording}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <StopCircle className="h-4 w-4" />
                      <span className="text-sm">Stop</span>
                    </button>
                    <button
                      onClick={retake}
                      disabled={!transcript || isRecording || submitted}
                      className="inline-flex items-center gap-2 px-3 py-2.5 rounded-lg border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span className="text-sm">Retake</span>
                    </button>
                  </div>

                  <div className="h-16 rounded-lg border border-white/10 bg-neutral-950/60 flex items-center px-3">
                    <div className="flex-1 flex items-end gap-1 h-12">
                      {[...Array(20)].map((_, i) => ( // Increased bars for effect
                        <span
                          key={i}
                          className={`w-1.5 rounded ${isRecording ? "bg-indigo-500/60 animate-pulse" : "bg-indigo-500/20"}`}
                          style={{ height: `${isRecording ? (10 + Math.random() * 80) : 10}%`, transition: 'height 0.2s', animationDelay: `${i * 50}ms` }}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-neutral-400 ml-3">{statusText}</span>
                  </div>

                  {transcript && (
                    <div className="rounded-lg border border-white/10 bg-neutral-950/60 p-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Headphones className="h-4 w-4 text-neutral-300" />
                          <span className="text-sm text-neutral-300">Transcription</span>
                        </div>
                        <span className="text-xs text-neutral-500">{transcript.trim().split(' ').length} words</span>
                      </div>
                      <div className="max-h-40 overflow-y-auto text-sm text-neutral-200 leading-relaxed">
                        {transcript}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    <button
                      onClick={submitAnswer}
                      disabled={!transcript || submitted || isProcessing || isRecording}
                      className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-emerald-500/30 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {isProcessing ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                      <span className="text-sm font-medium">
                        {isProcessing ? "Processing..." : "Submit Answer"}
                      </span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {interviewComplete && (
              <div className="rounded-xl border border-white/10 bg-white/5 p-6">
                <div className="flex items-start gap-3">
                  <div className="h-9 w-9 rounded-md bg-emerald-600/20 border border-emerald-500/30 grid place-items-center">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                  </div>
                  <div>
                    <h4 className="text-lg font-semibold">Interview Complete</h4>
                    <p className="text-sm text-neutral-400 mt-1">
                      Thank you, {name}! Your responses have been saved. Check interview_log.csv for the full transcript.
                    </p>
                    {/* --- ADDED: Button to go back to main screen --- */}
                    <button
                      onClick={() => onFinishInterview(sessionId)}
                      className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-indigo-500/30 bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
                    >
                      Finish Interview
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
