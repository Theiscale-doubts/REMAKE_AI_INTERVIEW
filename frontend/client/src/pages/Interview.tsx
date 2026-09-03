import { useState, useEffect, useRef } from "react";
import { useLocation } from "wouter";
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
  Volume2,
  Clock,
  ListChecks,
  AlertTriangle,
} from "lucide-react";
import PoweredByIScale from "@/components/PoweredByIScale";
const API_BASE_URL = `${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/api`;
const TOTAL_QUESTIONS = 9;
const IS_MAC = typeof navigator !== "undefined" && /Mac|iPod|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
const FULLSCREEN_SHORTCUT = IS_MAC ? "Control + Command + F" : "F11";

export default function VoxHireApp() {
  const [, setLocation] = useLocation();
  const [showInterview, setShowInterview] = useState(false);
  const [userDetails, setUserDetails] = useState({
    name: "",
    email: "",
    photo: null as string | null,
    role: "frontend",
  });
  const [sessionId, setSessionId] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const startNewSession = async () => {
    setStarting(true);
    setStartError(null);
    // Render free tier sleeps after inactivity — first request can take ~1 minute
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000);
    try {
      const codeParam = inviteCode.trim() ? `?code=${encodeURIComponent(inviteCode.trim())}` : "";
      const response = await fetch(`${API_BASE_URL}/start${codeParam}`, { signal: controller.signal });
      if (!response.ok) {
        // The server answered — show its actual message (e.g. invalid invite code)
        const data = await response.json().catch(() => ({}));
        setStartError(data.detail || "Something went wrong while starting your interview. Please try again.");
        return;
      }
      const data = await response.json();
      if (!data.session_id) throw new Error("No session_id in response");
      setSessionId(data.session_id);
      setShowInterview(true);
    } catch (error: any) {
      console.error("Failed to start session:", error);
      setStartError(
        error?.name === "AbortError"
          ? "The connection is taking longer than expected. Please try again in a moment."
          : "We couldn't reach the interview service. Please check your internet connection and try again."
      );
    } finally {
      clearTimeout(timeoutId);
      setStarting(false);
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
          setLocation(`/results/${finalSessionId}`);
        }}
      />
    );
  }

  return (
    <SetupPage
      userDetails={userDetails}
      setUserDetails={setUserDetails}
      onStart={startNewSession}
      starting={starting}
      startError={startError}
      inviteCode={inviteCode}
      setInviteCode={setInviteCode}
    />
  );
}

// --- SetupPage (No changes) ---
function SetupPage({
  userDetails,
  setUserDetails,
  onStart,
  starting,
  startError,
  inviteCode,
  setInviteCode,
}: {
  userDetails: { name: string; email: string; photo: string | null; role: string };
  setUserDetails: (details: any) => void;
  onStart: () => void;
  starting: boolean;
  startError: string | null;
  inviteCode: string;
  setInviteCode: (code: string) => void;
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
    // Request fullscreen here, inside the click handler — browsers only allow
    // requestFullscreen() in direct response to a user gesture like this one.
    document.documentElement.requestFullscreen?.().catch(() => {});
    onStart();
  };

  const roleLabel = userDetails.role.charAt(0).toUpperCase() + userDetails.role.slice(1).replace(/([A-Z])/g, " $1");

  return (
    <div className="min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-acc-cyan/40">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-6xl mx-auto px-7 h-16 flex items-center justify-between">
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold tracking-[0.1em]">VOXHIRE</span>
            <span className="text-[9.5px] font-medium tracking-[0.2em] text-txt-low uppercase">AI Interview Platform</span>
          </div>
          <PoweredByIScale />
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-7 py-8">
        <div className="max-w-[620px] mb-8 animate-fade-up">
          <div className="vh-badge mb-4">
            <span className="h-1.5 w-1.5 rounded-full bg-acc-cyan animate-pulse" />
            Step 1 of 2 · Interview setup
          </div>
          <h1 className="text-[2.1rem] md:text-[38px] tracking-[-0.03em] font-semibold leading-[1.08]">
            Set up your interview
          </h1>
          <p className="mt-3 text-base text-txt-mid leading-relaxed">
            Complete your details and pick a role. Your AI interviewer will speak
            each question aloud and listen to your answers.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_0.85fr] gap-6 items-start">
          {/* Left: candidate details */}
          <section className="vh-card-raised animate-fade-up" style={{ animationDelay: "0.08s" }}>
            <div className="px-7 pt-6 pb-5 border-b border-hairline">
              <h2 className="text-[17px] tracking-[-0.01em] font-semibold">Your details</h2>
              <p className="text-[13px] text-txt-mid mt-1">Tell us about yourself</p>
            </div>
            <div className="p-7 space-y-6">
              <div className="flex items-center gap-5">
                <div className="h-[76px] w-[76px] rounded-[14px] border border-hairline-strong bg-surface-2 overflow-hidden flex items-center justify-center flex-shrink-0">
                  {userDetails.photo ? (
                    <img src={userDetails.photo} alt="Profile" className="h-full w-full object-cover" />
                  ) : (
                    <User className="h-[26px] w-[26px] text-txt-low" />
                  )}
                </div>
                <div>
                  <label className="block text-[13px] font-medium text-txt-hi mb-2">Profile photo <span className="text-txt-low font-normal">(optional)</span></label>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="vh-btn-ghost px-4 py-2.5 text-[13px]"
                  >
                    <Upload className="h-3.5 w-3.5 text-txt-mid" />
                    Upload photo
                    <input type="file" accept="image/*" onChange={handlePhotoUpload} ref={fileInputRef} className="hidden" />
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-txt-hi mb-2">Full name <span className="text-[#C81D25]">*</span></label>
                <div className="relative">
                  <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low" />
                  <input
                    type="text"
                    value={userDetails.name}
                    onChange={(e) => setUserDetails({ ...userDetails, name: e.target.value })}
                    placeholder="Enter your full name"
                    className="vh-input text-[13.5px] pl-10 pr-4 py-3.5"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-txt-hi mb-2">Email address <span className="text-[#C81D25]">*</span></label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low" />
                  <input
                    type="email"
                    value={userDetails.email}
                    onChange={(e) => setUserDetails({ ...userDetails, email: e.target.value })}
                    placeholder="you@example.com"
                    className="vh-input text-[13.5px] pl-10 pr-4 py-3.5"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-txt-hi mb-2">Invite code</label>
                <div className="relative">
                  <Shield className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low" />
                  <input
                    type="text"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)}
                    placeholder="Enter the invite code you received"
                    className="vh-input text-[13.5px] pl-10 pr-4 py-3.5"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[13px] font-medium text-txt-hi mb-2">Job role <span className="text-[#C81D25]">*</span></label>
                <div className="relative">
                  <Briefcase className="absolute left-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low z-10" />
                  <select
                    value={userDetails.role}
                    onChange={(e) => setUserDetails({ ...userDetails, role: e.target.value })}
                    className="vh-input appearance-none text-[13.5px] pl-10 pr-10 py-3.5"
                  >
                    <option value="frontend">Front-End Developer</option>
                    <option value="datascience">Data Scientist</option>
                    <option value="data_analytics">Data Analytics</option>
                    <option value="product">Product Manager</option>
                    <option value="devops">DevOps Engineer</option>
                    <option value="hr">HR / Managerial</option>
                  </select>
                  <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-[15px] w-[15px] text-txt-low pointer-events-none" />
                </div>
                <p className="mt-2.5 text-[11.5px] text-txt-low leading-relaxed">
                  {roleLabel} — AI-generated questions tailored to this role, answered by voice.
                </p>
              </div>
            </div>

            <div className="px-7 py-6 border-t border-hairline bg-[rgba(5,5,5,.45)]">
              <button
                onClick={handleStartInterview}
                disabled={starting}
                className="vh-btn-primary w-full px-8 py-3.5 text-[15px]"
              >
                {starting ? (
                  <>
                    <Loader2 className="h-4.5 w-4.5 animate-spin" />
                    Starting your interview…
                  </>
                ) : (
                  <>
                    <Mic className="h-4.5 w-4.5" />
                    Start interview
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
              {starting && (
                <p className="mt-3.5 text-center text-sm text-txt-mid vh-shimmer-text">
                  Preparing your secure interview session — this can take up to a minute…
                </p>
              )}
              {startError && (
                <div className="mt-4 flex items-start gap-3 text-sm text-[#E05860] border border-[rgba(177,18,38,.3)] bg-[rgba(177,18,38,.08)] rounded-xl px-4 py-3.5">
                  <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <span>{startError}</span>
                </div>
              )}
            </div>
          </section>

          {/* Right: what to expect */}
          <div className="space-y-6 animate-fade-up" style={{ animationDelay: "0.16s" }}>
            <section className="vh-card p-7">
              <h2 className="text-[17px] tracking-[-0.01em] font-semibold mb-5">What to expect</h2>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { icon: ListChecks, label: "Questions", value: `${TOTAL_QUESTIONS} adaptive` },
                  { icon: Clock, label: "Duration", value: "≈ 15–20 min" },
                  { icon: Volume2, label: "AI interviewer", value: "Speaks aloud" },
                  { icon: Mic, label: "Your answers", value: "Voice, transcribed" },
                ].map(({ icon: Icon, label, value }) => (
                  <div key={label} className="rounded-xl border border-hairline bg-bg-2 p-4">
                    <Icon className="h-[15px] w-[15px] text-txt-low mb-2.5" />
                    <p className="text-[10px] uppercase tracking-[0.14em] text-txt-low">{label}</p>
                    <p className="text-[13.5px] font-medium text-txt-hi mt-0.5">{value}</p>
                  </div>
                ))}
              </div>
              <div className="mt-5 space-y-2.5">
                <div className="flex items-center gap-2.5 text-[13px] text-txt-mid">
                  <Camera className="h-[15px] w-[15px] text-acc-emerald flex-shrink-0" />
                  Camera & microphone access is requested when the interview begins
                </div>
                <div className="flex items-center gap-2.5 text-[13px] text-txt-mid">
                  <CheckCircle2 className="h-[15px] w-[15px] text-acc-emerald flex-shrink-0" />
                  Works best in Chrome or Edge on desktop
                </div>
              </div>
            </section>

            <section className="vh-card p-7">
              <h2 className="text-[14.5px] tracking-[-0.01em] font-semibold mb-4">Preparation tips</h2>
              <ul className="space-y-3">
                {[
                  "Find a quiet, well-lit spot — the session is proctored by camera.",
                  "Answer out loud in full sentences; explain the why, not just the what.",
                  "Stay on this tab. Tab switches are recorded in your report.",
                  "You can replay any question with the speaker button.",
                ].map((tip, i) => (
                  <li key={i} className="flex items-start gap-3 text-[13px] leading-relaxed text-txt-mid">
                    <span className="h-5 w-5 rounded-md bg-surface-2 border border-hairline grid place-items-center text-[10px] font-semibold text-[#C81D25] flex-shrink-0 mt-0.5 tabular-nums">
                      {i + 1}
                    </span>
                    {tip}
                  </li>
                ))}
              </ul>
            </section>

            <div className="flex items-start gap-3 px-5 py-4 rounded-2xl border border-hairline bg-surface-1/60">
              <Shield className="h-[15px] w-[15px] text-txt-low mt-0.5 flex-shrink-0" />
              <p className="text-[11.5px] leading-relaxed text-txt-low">
                Your responses are transcribed and saved securely for evaluation.
                Audio is processed for transcription only and never stored.
              </p>
            </div>
          </div>
        </div>
      </main>

      <footer className="border-t border-hairline mt-6">
        <div className="max-w-6xl mx-auto px-7 py-[18px] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 text-[13px] text-txt-low">
          <p>© {new Date().getFullYear()} VoxHire. All rights reserved.</p>
          <PoweredByIScale />
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);
  const [questionCount, setQuestionCount] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const intervalIdRef = useRef<number | null>(null);
  const elapsedIntervalRef = useRef<number | null>(null);
  const isRecordingRef = useRef(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  // Interview-time webcam snapshot: captured once, sent once with the first save.
  const capturedPhotoRef = useRef<string | null>(null);
  const photoSentRef = useRef(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const levelIntervalRef = useRef<number | null>(null);
  const peakLevelRef = useRef(0);
  const [micLevels, setMicLevels] = useState<number[]>(Array(20).fill(0));

  const [cameraStream, setCameraStream] = useState<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [tabSwitches, setTabSwitches] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(() => !!document.fullscreenElement);
  const [faceStatus, setFaceStatus] = useState<"loading" | "detected" | "none" | "unavailable">("loading");
  const faceDetectorRef = useRef<{ close: () => void } | null>(null);
  const [proctorStats, setProctorStats] = useState({
    faceLostCount: 0,
    faceLostSeconds: 0,
    multipleFacesCount: 0,
    movementEvents: 0,
  });
  // Transition tracking between detection frames (refs to avoid re-render churn)
  const proctorRef = useRef({
    lastFaceCount: -1,
    faceLostAt: null as number | null,
    lastCenter: null as { x: number; y: number; t: number } | null,
    wasNearEdge: false,
  });

  // Proctoring: detect whether a face is visible in the camera feed.
  // Recording is blocked while no face is detected; degrades gracefully
  // (recording allowed) if the detector fails to load.
  useEffect(() => {
    if (!cameraStream) return;
    let cancelled = false;
    let intervalId: number | undefined;
    (async () => {
      try {
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks(
          "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304/wasm"
        );
        const detector = await vision.FaceDetector.createFromOptions(fileset, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
          },
          runningMode: "VIDEO",
        });
        if (cancelled) {
          detector.close();
          return;
        }
        faceDetectorRef.current = detector;
        intervalId = window.setInterval(() => {
          const video = videoRef.current;
          if (!video || video.readyState < 2) return;
          try {
            const result = detector.detectForVideo(video, performance.now());
            const detections = result.detections;
            const count = detections.length;
            const now = performance.now();
            const p = proctorRef.current;

            setFaceStatus(count > 0 ? "detected" : "none");

            // Second person in frame (transition into >1 faces, including the first frame)
            if (count > 1 && p.lastFaceCount <= 1) {
              setProctorStats((s) => ({ ...s, multipleFacesCount: s.multipleFacesCount + 1 }));
            }

            // Face absence: count each disappearance and how long it lasted
            if (count === 0 && p.lastFaceCount > 0) {
              p.faceLostAt = now;
            }
            if (count > 0 && p.lastFaceCount === 0 && p.faceLostAt !== null) {
              const seconds = (now - p.faceLostAt) / 1000;
              p.faceLostAt = null;
              setProctorStats((s) => ({
                ...s,
                faceLostCount: s.faceLostCount + 1,
                faceLostSeconds: s.faceLostSeconds + seconds,
              }));
            }
            p.lastFaceCount = count;

            // Out-of-frame drift and sudden position jumps (bounding box geometry)
            const box = count > 0 ? detections[0].boundingBox : undefined;
            if (box && video.videoWidth > 0 && video.videoHeight > 0) {
              const cx = (box.originX + box.width / 2) / video.videoWidth;
              const cy = (box.originY + box.height / 2) / video.videoHeight;
              const margin = 0.07;
              const nearEdge =
                cx < margin || cx > 1 - margin || cy < margin || cy > 1 - margin ||
                box.originX <= 2 || box.originY <= 2 ||
                box.originX + box.width >= video.videoWidth - 2 ||
                box.originY + box.height >= video.videoHeight - 2;
              let jumped = false;
              if (p.lastCenter && now - p.lastCenter.t < 2500) {
                jumped = Math.hypot(cx - p.lastCenter.x, cy - p.lastCenter.y) > 0.3;
              }
              if ((nearEdge && !p.wasNearEdge) || jumped) {
                setProctorStats((s) => ({ ...s, movementEvents: s.movementEvents + 1 }));
              }
              p.wasNearEdge = nearEdge;
              p.lastCenter = { x: cx, y: cy, t: now };
            } else {
              p.lastCenter = null;
              p.wasNearEdge = false;
            }
          } catch (_) {
            // Detection hiccup on a single frame — keep previous status
          }
        }, 800);
      } catch (err) {
        console.error("Face detection unavailable:", err);
        if (!cancelled) setFaceStatus("unavailable");
      }
    })();
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
      faceDetectorRef.current?.close();
      faceDetectorRef.current = null;
    };
  }, [cameraStream]);

  // Proctoring: count how many times the candidate leaves this tab
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.hidden) setTabSwitches((c) => c + 1);
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  // Fullscreen-only mode: the interview is blocked (see the overlay in the
  // render below) whenever the candidate is not in fullscreen — this fires
  // on Esc, F11, swiping away, or the browser exiting fullscreen for any
  // other reason.
  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const requestFullscreen = () => {
    document.documentElement.requestFullscreen?.().catch(() => {});
  };

  // If the candidate exits fullscreen mid-answer, stop the recording rather
  // than letting it keep running behind the blocking overlay.
  useEffect(() => {
    if (!isFullscreen && isRecordingRef.current) {
      stopRecording();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFullscreen]);

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
        // If the camera is turned off / unplugged / permission revoked
        // mid-interview, the track ends — surface it so recording is blocked.
        s.getVideoTracks().forEach((t) => {
          t.onended = () => {
            setCameraError("Your camera turned off. Please re-enable it and refresh the page to continue.");
          };
        });
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

  const pickVoice = (): SpeechSynthesisVoice | null => {
    const voices = window.speechSynthesis.getVoices();
    // Prefer the most natural-sounding English voices available on this browser
    const preferred = [
      "Google US English",
      "Microsoft Aria",
      "Microsoft Jenny",
      "Microsoft Zira",
      "Google UK English Female",
    ];
    for (const name of preferred) {
      const match = voices.find((v) => v.name.includes(name));
      if (match) return match;
    }
    return voices.find((v) => v.lang?.startsWith("en")) || null;
  };

  const speakQuestion = (text: string) => {
    if (!text || !("speechSynthesis" in window)) return;
    const doSpeak = () => {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      utterance.lang = "en-US";
      utterance.rate = 0.95;
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
    };
    // Chrome loads voices asynchronously; wait for them once so the first
    // question uses the natural voice instead of the robotic default.
    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        doSpeak();
      };
      // Fallback in case voiceschanged never fires
      setTimeout(() => {
        if (window.speechSynthesis.onvoiceschanged) {
          window.speechSynthesis.onvoiceschanged = null;
          doSpeak();
        }
      }, 1500);
      return;
    }
    doSpeak();
  };

  const stopSpeaking = () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  };

  // Speak each question aloud when it appears; stop speech when leaving the page
  useEffect(() => {
    if (!interviewComplete) speakQuestion(currentQuestion);
    return () => stopSpeaking();
  }, [currentQuestion, interviewComplete]);

  // Set first question and clean up on unmount
  useEffect(() => {
    setCurrentQuestion("Introduce yourself.");
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        try { mediaRecorderRef.current.stop(); } catch (_) {}
      }
      if (intervalIdRef.current) clearInterval(intervalIdRef.current);
    };
  }, []);

  // Continuous interview clock — counts total elapsed time from the start of
  // the interview, independent of per-question recording. Stops when complete.
  useEffect(() => {
    if (interviewComplete) {
      if (elapsedIntervalRef.current) {
        clearInterval(elapsedIntervalRef.current);
        elapsedIntervalRef.current = null;
      }
      return;
    }
    elapsedIntervalRef.current = window.setInterval(() => {
      setElapsedSeconds((s) => s + 1);
    }, 1000);
    return () => {
      if (elapsedIntervalRef.current) {
        clearInterval(elapsedIntervalRef.current);
        elapsedIntervalRef.current = null;
      }
    };
  }, [interviewComplete]);

  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60).toString().padStart(2, "0");
    const s = Math.floor(sec % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  const startRecording = async () => {
    // Proctoring requires the camera. The button stays clickable so the
    // candidate always gets this warning — but recording never proceeds
    // until the camera is back, no matter how many times they click.
    if (cameraError) {
      showCustomAlert(
        "Your camera is required for this proctored interview. Please enable camera access and refresh the page before recording."
      );
      return;
    }
    if (faceStatus === "none") {
      showCustomAlert(
        "No face detected. Please turn on your camera and sit facing it with good lighting, then try again."
      );
      return;
    }

    // Silence the interviewer voice so the mic doesn't pick it up
    stopSpeaking();

    if (!window.isSecureContext) {
      showCustomAlert("Recording requires a secure (HTTPS) connection. Please open this site over https://");
      return;
    }

    let micStream: MediaStream;
    try {
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
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

    audioChunksRef.current = [];
    const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/ogg";
    const recorder = new MediaRecorder(micStream, { mimeType });

    // Live mic level meter so the user can see the mic is actually picking up sound
    try {
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(micStream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      audioCtxRef.current = audioCtx;
      const data = new Uint8Array(analyser.frequencyBinCount);
      levelIntervalRef.current = window.setInterval(() => {
        analyser.getByteTimeDomainData(data);
        let sum = 0;
        for (let i = 0; i < data.length; i++) {
          const v = (data[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / data.length);
        peakLevelRef.current = Math.max(peakLevelRef.current, rms);
        setMicLevels((prev) => [...prev.slice(1), Math.min(1, rms * 4)]);
      }, 100);
    } catch (_) {
      // Meter is cosmetic; recording still works without it
    }

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      micStream.getTracks().forEach((t) => t.stop());
      if (levelIntervalRef.current) {
        clearInterval(levelIntervalRef.current);
        levelIntervalRef.current = null;
      }
      audioCtxRef.current?.close().catch(() => {});
      audioCtxRef.current = null;
      setMicLevels(Array(20).fill(0));

      // If the mic never registered any sound, don't bother Whisper — it would
      // hallucinate filler like "Thank you." on silent audio.
      if (peakLevelRef.current < 0.02) {
        setTranscript("");
        setStatusText("Your microphone recorded only silence. Check Chrome is using your real mic (site settings), then retake.");
        return;
      }

      const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
      setStatusText("Transcribing your answer...");

      try {
        const formData = new FormData();
        formData.append("file", audioBlob, `recording.${mimeType === "audio/webm" ? "webm" : "ogg"}`);
        const res = await fetch(`${API_BASE_URL}/transcribe`, { method: "POST", body: formData });
        if (!res.ok) throw new Error("Transcription request failed");
        const data = await res.json();
        if (data.warning === "no_speech_detected" || !data.transcript) {
          setTranscript("");
          setStatusText("No speech detected — check your microphone and retake.");
          return;
        }
        setTranscript(data.transcript);
        setStatusText("Transcription complete — review and submit.");
      } catch (err) {
        console.error("Transcription error:", err);
        setStatusText("Transcription failed. Please retake and try again.");
        isRecordingRef.current = false;
        setIsRecording(false);
      }
    };

    mediaRecorderRef.current = recorder;
    peakLevelRef.current = 0;
    recorder.start();
    isRecordingRef.current = true;
    setIsRecording(true);
    setTranscript("");
    setTotalSeconds(0);
    setSubmitted(false);
    setStatusText("Recording — speak your answer...");

    intervalIdRef.current = window.setInterval(() => {
      setTotalSeconds((prev) => prev + 1);
    }, 1000);
  };

  const stopRecording = () => {
    if (intervalIdRef.current) {
      clearInterval(intervalIdRef.current);
      intervalIdRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    isRecordingRef.current = false;
    setIsRecording(false);
  };

  const retake = () => {
    setTranscript("");
    setTotalSeconds(0);
    setStatusText("Ready to record");
    setSubmitted(false);
  };

  // Grab a single downscaled JPEG frame from the live proctoring feed. Cached so
  // it only runs once, and fully guarded so any failure just yields null (no
  // photo) rather than disrupting the interview.
  const captureSnapshot = (): string | null => {
    if (capturedPhotoRef.current) return capturedPhotoRef.current;
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) return null;
    try {
      const targetW = 320;
      const scale = targetW / video.videoWidth;
      const canvas = document.createElement("canvas");
      canvas.width = targetW;
      canvas.height = Math.round(video.videoHeight * scale);
      const ctx = canvas.getContext("2d");
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
      capturedPhotoRef.current = dataUrl;
      return dataUrl;
    } catch {
      return null;
    }
  };

  const submitAnswer = async () => {
    if (!transcript.trim()) {
      showCustomAlert("Please record an answer before submitting.");
      return;
    }

    setIsProcessing(true);
    setSubmitted(true); // Lock submit button
    setStatusText("Submitting...");

    // Capture the verification snapshot once, and only attach it to a single
    // save so we don't re-upload the image on every answer.
    let photoForThisSave: string | null = null;
    if (!photoSentRef.current) {
      photoForThisSave = captureSnapshot();
      if (photoForThisSave) photoSentRef.current = true;
    }

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
          role: role,
          tab_switches: tabSwitches,
          face_lost_count: proctorStats.faceLostCount,
          face_lost_seconds: Math.round(proctorStats.faceLostSeconds),
          multiple_faces_count: proctorStats.multipleFacesCount,
          movement_events: proctorStats.movementEvents,
          photo: photoForThisSave
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
    <div className="min-h-screen bg-ink text-txt-hi font-display antialiased selection:bg-acc-cyan/40">
      {/* Fullscreen gate — blocks the entire interview whenever the candidate
          is not in fullscreen. Sits above everything else (z-50) so nothing
          underneath is reachable until fullscreen is restored. */}
      {!isFullscreen && !interviewComplete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/95 backdrop-blur-md px-6">
          <div className="vh-card max-w-md w-full p-7 text-center">
            <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-[rgba(177,18,38,.1)] border border-[rgba(177,18,38,.25)] flex items-center justify-center">
              <AlertTriangle className="h-6 w-6 text-[#E05860]" />
            </div>
            <h2 className="text-[17px] font-bold text-txt-hi">Fullscreen required</h2>
            <p className="mt-2 text-[13.5px] leading-relaxed text-txt-low">
              This interview only runs in fullscreen mode to keep proctoring active. Recording is paused while you're out of fullscreen — return to continue.
            </p>
            <button
              onClick={requestFullscreen}
              className="mt-5 w-full px-5 py-3 text-[13.5px] rounded-xl font-semibold vh-btn-primary"
            >
              Enter Fullscreen
            </button>
            <p className="mt-3 text-[11.5px] text-txt-low">
              Or press <span className="font-semibold text-txt-mid">{FULLSCREEN_SHORTCUT}</span> on your keyboard
            </p>
          </div>
        </div>
      )}

      {/* Proctoring monitor — fixed top-right */}
      <div className="fixed top-[84px] right-4 z-10 w-[212px] vh-card overflow-hidden">
        <div className="px-3.5 py-2.5 flex items-center justify-between border-b border-hairline bg-surface-2/70">
          <span className="flex items-center gap-2 text-[11px] font-medium text-txt-mid uppercase tracking-[0.1em]">
            <Camera className="h-3.5 w-3.5 text-txt-low" />
            Proctoring
          </span>
          {!cameraError && faceStatus === "detected" && (
            <span className="h-1.5 w-1.5 rounded-full bg-acc-emerald animate-pulse" />
          )}
        </div>
        <div className="relative bg-black" style={{ height: 150 }}>
          {cameraError ? (
            <div className="h-full flex flex-col items-center justify-center gap-2 px-2">
              <CameraOff className="h-7 w-7 text-[#E05860]/60" />
              <span className="text-xs text-[#E05860] text-center">Camera unavailable</span>
            </div>
          ) : (
            <video ref={videoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          )}
        </div>
        {cameraError && (
          <div className="px-3.5 py-2 bg-[rgba(177,18,38,.1)] border-t border-[rgba(177,18,38,.2)]">
            <p className="text-[11px] leading-snug text-[#DFA2A8]">{cameraError}</p>
          </div>
        )}
        {!cameraError && (
          <div className={`px-3.5 py-1.5 border-t border-hairline ${
            faceStatus === "detected" ? "bg-[rgba(95,164,127,.06)]" : faceStatus === "none" ? "bg-[rgba(177,18,38,.1)]" : "bg-surface-2/50"
          }`}>
            <p className={`text-[11px] ${
              faceStatus === "detected" ? "text-acc-emerald" : faceStatus === "none" ? "text-[#E05860]" : "text-txt-low"
            }`}>
              {faceStatus === "detected" && "Face detected"}
              {faceStatus === "none" && "No face detected"}
              {faceStatus === "loading" && "Starting face check…"}
              {faceStatus === "unavailable" && "Face check unavailable"}
            </p>
          </div>
        )}
        <div className={`px-3.5 py-1.5 border-t border-hairline ${tabSwitches > 0 ? "bg-amber-500/10" : "bg-surface-2/50"}`}>
          <p className={`text-[11px] ${tabSwitches > 0 ? "text-amber-400" : "text-txt-low"}`}>
            Tab switches: {tabSwitches}
          </p>
        </div>
        {(proctorStats.faceLostCount > 0 || proctorStats.multipleFacesCount > 0 || proctorStats.movementEvents > 0) && (
          <div className="px-3.5 py-1.5 border-t border-hairline bg-amber-500/10">
            <p className="text-[11px] leading-relaxed text-amber-400">
              {proctorStats.faceLostCount > 0 && `Left view: ${proctorStats.faceLostCount}× `}
              {proctorStats.multipleFacesCount > 0 && `· Multiple faces: ${proctorStats.multipleFacesCount}× `}
              {proctorStats.movementEvents > 0 && `· Movement: ${proctorStats.movementEvents}×`}
            </p>
          </div>
        )}
      </div>

      <header className="sticky top-0 z-20 backdrop-blur-xl bg-ink/[.82] border-b border-hairline">
        <div className="max-w-6xl mx-auto px-7 h-16 flex items-center justify-between">
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold tracking-[0.1em]">VOXHIRE</span>
            <span className="text-[9.5px] font-medium tracking-[0.2em] text-txt-low uppercase">{roleLabel} interview</span>
          </div>
          <div className="flex items-center gap-5">
            <span className="hidden md:inline-flex vh-badge tabular-nums">
              <span className="h-1.5 w-1.5 rounded-full bg-acc-cyan animate-pulse" />
              {formatTime(elapsedSeconds)}
            </span>
            <div className="hidden sm:flex items-center gap-3">
              {photo && <img src={photo} alt={name} className="h-8 w-8 rounded-full object-cover border border-hairline-strong" />}
              <div className="text-right leading-tight">
                <p className="text-[13.5px] font-medium">{name}</p>
                <p className="text-[11px] text-txt-low">{email}</p>
              </div>
            </div>
            <button onClick={onBack} className="text-[13px] text-txt-mid hover:text-txt-hi transition-colors">Exit</button>
          </div>
        </div>
        {/* Progress */}
        {!interviewComplete && (
          <div className="h-0.5 bg-surface-2">
            <div
              className="h-full transition-all duration-700 ease-out"
              style={{
                width: `${((questionCount + 1) / TOTAL_QUESTIONS) * 100}%`,
                background: "linear-gradient(90deg,#6E0F1E,#B11226)",
              }}
            />
          </div>
        )}
      </header>

      <main className="max-w-6xl mx-auto px-7 py-10 space-y-6 md:pr-[248px] lg:pr-[264px]">
        {isProcessing && !currentQuestion && !interviewComplete ? (
          <div className="vh-card-raised p-12 text-center animate-fade-up">
            <Loader2 className="h-8 w-8 animate-spin mx-auto mb-5 text-acc-cyan" />
            <p className="text-txt-mid vh-shimmer-text">Preparing your interview…</p>
          </div>
        ) : (
          <>
            {!interviewComplete && (
              <div key={questionCount} className="animate-fade-up space-y-6">
                {/* Question — the centerpiece */}
                <div className="vh-card-raised overflow-hidden">
                  <div className="px-8 pt-8 pb-7">
                    <div className="flex items-center gap-3 mb-5">
                      <span className="inline-flex items-center gap-2 rounded-full border border-[rgba(177,18,38,.4)] bg-[rgba(177,18,38,.08)] px-3.5 py-1.5 text-[11.5px] font-semibold text-[#E05860] tabular-nums tracking-[0.04em]">
                        QUESTION {questionCount + 1} OF {TOTAL_QUESTIONS}
                      </span>
                      <span className="text-xs text-txt-low">Voice answer</span>
                    </div>
                    <div className="flex items-start gap-4">
                      <h3 className="flex-1 text-2xl md:text-[26px] leading-[1.35] tracking-[-0.02em] font-semibold text-txt-hi">
                        {currentQuestion}
                      </h3>
                      <button
                        onClick={() => (isSpeaking ? stopSpeaking() : speakQuestion(currentQuestion))}
                        disabled={isRecording}
                        title={isSpeaking ? "Stop speaking" : "Replay question"}
                        className={`flex-shrink-0 h-11 w-11 grid place-items-center rounded-xl border transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${
                          isSpeaking
                            ? "border-[rgba(200,29,37,.5)] bg-surface-1 text-txt-hi"
                            : "border-hairline-strong bg-surface-1 text-txt-mid hover:border-[rgba(200,29,37,.5)] hover:text-txt-hi"
                        }`}
                      >
                        <Volume2 className="h-4.5 w-4.5" />
                      </button>
                    </div>
                    {isSpeaking && (
                      <p className="mt-3 text-xs text-txt-mid flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-acc-cyan animate-pulse" />
                        Interviewer is speaking…
                      </p>
                    )}
                  </div>

                  {/* Waveform stage */}
                  <div className="px-8 pb-8">
                    <div
                      className="rounded-2xl border transition-colors duration-500"
                      style={{
                        borderColor: isRecording ? "rgba(177,18,38,.28)" : "rgba(255,255,255,0.06)",
                        background: isRecording
                          ? "radial-gradient(80% 100% at 50% 0%, rgba(177,18,38,.06), transparent 70%), #0B0B0C"
                          : "#0B0B0C",
                      }}
                    >
                      <div className="flex items-end justify-center gap-[5px] h-24 px-6 pt-5">
                        {micLevels.map((level, i) => (
                          <span
                            key={i}
                            className="w-2 rounded-full transition-colors duration-300"
                            style={{
                              height: `${8 + level * 92}%`,
                              transition: "height 0.1s ease-out, background 0.3s",
                              background: isRecording ? `rgba(200,29,37,${(0.35 + level * 0.65).toFixed(2)})` : "#1E1F23",
                            }}
                          />
                        ))}
                      </div>
                      <div className="flex items-center justify-between px-5 py-3 border-t border-hairline/60 mt-4 bg-[rgba(5,5,5,.35)]">
                        <span
                          className="inline-flex items-center gap-2 text-xs font-medium"
                          style={{
                            color: isRecording
                              ? "#DFA2A8"
                              : isProcessing || statusText.includes("Transcribing")
                                ? "#B3B3B8"
                                : "#7C7C84",
                          }}
                        >
                          {isRecording && (
                            <span
                              className="h-2 w-2 rounded-full bg-acc-cyan animate-pulse"
                              style={{ boxShadow: "0 0 0 3px rgba(177,18,38,.15)" }}
                            />
                          )}
                          {(isProcessing || statusText.includes("Transcribing")) && <Loader2 className="h-3 w-3 animate-spin" />}
                          {statusText}
                        </span>
                        {isRecording && (
                          <span className="inline-flex items-center gap-2 rounded-full border border-[rgba(177,18,38,.3)] bg-[rgba(177,18,38,.07)] px-3 py-1 text-[10.5px] font-semibold tracking-[0.12em] text-[#C4818A]">
                            REC
                            <span className="tabular-nums font-medium tracking-[0.04em] text-[#DFA2A8]">{formatTime(totalSeconds)}</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Controls */}
                    <div className="mt-6 flex items-center gap-3 flex-wrap">
                      <button
                        onClick={startRecording}
                        disabled={isRecording || submitted || isProcessing || !isFullscreen}
                        className={`px-5 py-3 text-[13.5px] rounded-xl font-semibold inline-flex items-center gap-2 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed ${
                          isRecording
                            ? "bg-[rgba(177,18,38,.08)] border border-[rgba(177,18,38,.4)] text-[#DFA2A8]"
                            : "vh-btn-primary"
                        }`}
                      >
                        <Mic className="h-4 w-4" />
                        {isRecording ? "Recording…" : "Start recording"}
                      </button>
                      <button
                        onClick={stopRecording}
                        disabled={!isRecording}
                        className="vh-btn-ghost px-5 py-3 text-[13.5px]"
                      >
                        <StopCircle className="h-4 w-4 text-txt-mid" />
                        Stop
                      </button>
                      <button
                        onClick={retake}
                        disabled={!transcript || isRecording || submitted}
                        className="vh-btn-ghost px-4 py-3 text-[13.5px]"
                      >
                        <RotateCcw className="h-4 w-4 text-txt-mid" />
                        Retake
                      </button>
                      <div className="flex-1" />
                      <button
                        onClick={submitAnswer}
                        disabled={!transcript || submitted || isProcessing || isRecording}
                        className="vh-btn-primary px-6 py-3 text-[13.5px]"
                      >
                        {isProcessing ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Processing…
                          </>
                        ) : (
                          <>
                            <Send className="h-4 w-4" />
                            Submit answer
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Transcript */}
                {transcript && (
                  <div className="vh-card p-6 animate-fade-up">
                    <div className="flex items-center justify-between mb-3">
                      <span className="flex items-center gap-2.5 text-[13.5px] font-semibold text-txt-hi">
                        <Headphones className="h-4 w-4 text-acc-emerald" />
                        Your answer
                      </span>
                      <span className="vh-badge tabular-nums">{transcript.trim().split(" ").length} words</span>
                    </div>
                    <div className="max-h-44 overflow-y-auto text-[14.5px] text-txt-mid leading-[1.7]">
                      {transcript}
                    </div>
                  </div>
                )}
              </div>
            )}

            {interviewComplete && (
              <div className="vh-card-raised p-10 text-center animate-fade-up">
                <div className="mx-auto h-16 w-16 rounded-2xl bg-[rgba(95,164,127,.08)] border border-[rgba(95,164,127,.3)] grid place-items-center mb-6">
                  <CheckCircle2 className="h-[30px] w-[30px] text-acc-emerald" />
                </div>
                <h4 className="text-2xl tracking-[-0.02em] font-semibold">Interview complete</h4>
                <p className="mt-3 max-w-md mx-auto text-[14.5px] leading-relaxed text-txt-mid">
                  Thank you, {name}! Your responses have been saved and your
                  evaluation is ready to generate.
                </p>
                <button
                  onClick={() => onFinishInterview(sessionId)}
                  className="vh-btn-primary mt-8 px-8 py-3.5 text-[15px]"
                >
                  View my results
                  <ArrowRight className="h-4 w-4" />
                </button>
                <div className="mt-6 flex justify-center"><PoweredByIScale /></div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
