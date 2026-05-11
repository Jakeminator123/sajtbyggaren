"use client";

import { useState, useRef, useCallback } from "react";
import { Mic, MicOff, Loader2, Square, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import styles from "./voice-recorder.module.css";

interface VoiceRecorderProps {
  onTranscript: (transcript: string) => void;
  onRecordingChange?: (isRecording: boolean) => void;
  language?: "sv" | "en";
  placeholder?: string;
  className?: string;
  /** Compact mode: renders a small icon button that fits into toolbars */
  compact?: boolean;
  disabled?: boolean;
}

export function VoiceRecorder({
  onTranscript,
  onRecordingChange,
  language = "sv",
  placeholder = "Klicka för att börja prata...",
  className = "",
  compact = false,
  disabled = false,
}: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const audioLevelStep = Math.max(0, Math.min(10, Math.round(audioLevel * 10)));
  const levelClasses = [
    styles.level0,
    styles.level1,
    styles.level2,
    styles.level3,
    styles.level4,
    styles.level5,
    styles.level6,
    styles.level7,
    styles.level8,
    styles.level9,
    styles.level10,
  ];
  const barIndexClasses = [
    styles.barIndex1,
    styles.barIndex2,
    styles.barIndex3,
    styles.barIndex4,
    styles.barIndex5,
  ];
  const levelClass = levelClasses[audioLevelStep];

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationRef = useRef<number | null>(null);
  const transcribeAudioRef = useRef<((audioBlob: Blob) => Promise<void>) | null>(null);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      setError(null);

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      });

      // Setup audio analysis for visual feedback
      const audioContext = new AudioContext();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      // Animate audio level
      const updateAudioLevel = () => {
        if (analyserRef.current) {
          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(dataArray);
          const average = dataArray.reduce((a, b) => a + b) / dataArray.length;
          setAudioLevel(average / 255);
        }
        animationRef.current = requestAnimationFrame(updateAudioLevel);
      };
      updateAudioLevel();

      // Setup MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Stop audio analysis
        if (animationRef.current) {
          cancelAnimationFrame(animationRef.current);
        }
        setAudioLevel(0);

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop());

        // Create blob from chunks
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });

        // Transcribe the audio
        await transcribeAudioRef.current?.(audioBlob);
      };

      // Start recording
      mediaRecorder.start(1000); // Collect data every second
      setIsRecording(true);
      setRecordingTime(0);
      onRecordingChange?.(true);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error("Failed to start recording:", err);
      if (err instanceof Error && err.name === "NotAllowedError") {
        setError("Mikrofon-åtkomst nekad. Tillåt mikrofonen i webbläsaren.");
      } else {
        setError("Kunde inte starta inspelning. Kontrollera din mikrofon.");
      }
    }
  }, [onRecordingChange]);

  // Transcribe audio using Whisper API
  const transcribeAudio = useCallback(
    async (audioBlob: Blob) => {
      setIsTranscribing(true);
      setError(null);

      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");
        formData.append("language", language);

        const response = await fetch("/api/transcribe", {
          method: "POST",
          body: formData,
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(data.error || "Transkribering misslyckades");
        }

        if (data.transcript) {
          onTranscript(data.transcript);
        } else {
          setError("Inget tal upptäcktes. Försök igen.");
        }
      } catch (err) {
        console.error("Transcription error:", err);
        setError(err instanceof Error ? err.message : "Kunde inte transkribera. Försök igen.");
      } finally {
        setIsTranscribing(false);
      }
    },
    [language, onTranscript],
  );
  transcribeAudioRef.current = transcribeAudio;

  // Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      onRecordingChange?.(false);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [isRecording, onRecordingChange]);

  // Format recording time
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // ── Compact mode ──────────────────────────────────────────────────
  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1.5 ${className}`}>
        <button
          type="button"
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isTranscribing || disabled}
          title={
            isTranscribing
              ? "Transkriberar..."
              : isRecording
                ? `Stoppa inspelning (${formatTime(recordingTime)})`
                : "Spela in röstmeddelande"
          }
          className={`relative inline-flex h-7 w-7 items-center justify-center rounded-md border transition-all ${
            isRecording
              ? "border-red-500 bg-red-500/20 text-red-400 hover:bg-red-500/30"
              : isTranscribing
                ? "border-border text-muted-foreground cursor-wait opacity-60"
                : "border-border text-muted-foreground hover:bg-accent hover:text-foreground"
          } disabled:opacity-50`}
        >
          {isTranscribing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : isRecording ? (
            <Square className="h-3 w-3 fill-current" />
          ) : (
            <Mic className="h-3.5 w-3.5" />
          )}

          {/* Pulse ring when recording */}
          {isRecording && (
            <span className="absolute inset-0 animate-ping rounded-md border border-red-400/40" />
          )}
        </button>

        {/* Show timer when recording */}
        {isRecording && (
          <span className="text-xs font-mono text-red-400">{formatTime(recordingTime)}</span>
        )}

        {/* Compact audio bars */}
        {isRecording && (
          <div className="flex items-center gap-0.5">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className={`w-0.5 rounded-full bg-red-500 transition-all ${styles.audioBar} ${barIndexClasses[i]} ${levelClass} ${
                  audioLevel > i * 0.3 ? styles.barActive : styles.barInactive
                }`}
                style={{ height: `${8 + audioLevel * (4 + i * 3)}px` }}
              />
            ))}
          </div>
        )}

        {/* Compact error tooltip */}
        {error && (
          <span className="text-xs text-red-400" title={error}>
            <MicOff className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
    );
  }

  // ── Full mode ─────────────────────────────────────────────────────
  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <div className="flex items-center gap-3">
        {/* Main record button */}
        <Button
          type="button"
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isTranscribing || disabled}
          variant={isRecording ? "destructive" : "outline"}
          size="lg"
          className={`relative min-w-[180px] gap-2 transition-all ${
            isRecording
              ? "border-red-600 bg-red-600 hover:bg-red-700"
              : "border-primary/50 text-primary hover:bg-primary/10 hover:text-primary/80"
          }`}
        >
          {isTranscribing ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Transkriberar...
            </>
          ) : isRecording ? (
            <>
              <Square className="h-4 w-4 fill-current" />
              Stoppa ({formatTime(recordingTime)})
            </>
          ) : (
            <>
              <Mic className="h-5 w-5" />
              {placeholder}
            </>
          )}

          {/* Audio level indicator */}
          {isRecording && (
            <div
              className={`absolute inset-0 origin-left rounded-md bg-red-400/20 transition-transform ${styles.audioLevelIndicator} ${levelClass}`}
            />
          )}
        </Button>

        {/* Visual audio level bars */}
        {isRecording && (
          <div className="flex items-center gap-1">
            {[...Array(5)].map((_, i) => (
              <div
                key={i}
                className={`w-1 rounded-full bg-red-500 transition-all ${styles.audioBar} ${barIndexClasses[i]} ${levelClass} ${
                  audioLevel > i * 0.2 ? styles.barActive : styles.barInactive
                }`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-red-400">
          <MicOff className="h-4 w-4" />
          {error}
        </div>
      )}

      {/* Recording hint */}
      {!isRecording && !isTranscribing && !error && (
        <p className="text-xs text-muted-foreground">
          <Volume2 className="mr-1 inline h-3 w-3" />
          Beskriv din webbplats med rösten – vi transkriberar automatiskt
        </p>
      )}
    </div>
  );
}
