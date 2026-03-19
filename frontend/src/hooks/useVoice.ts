/**
 * useVoice.ts - Custom hook cho Voice Interaction
 * Quản lý ghi âm (STT) và phát audio (TTS)
 */

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { synthesizeSpeech, transcribeAudio } from "@/lib/api";

interface UseVoiceReturn {
  /** Đang ghi âm */
  isRecording: boolean;
  /** Đang phát TTS */
  isPlaying: boolean;
  /** Đang xử lý (transcribe/synthesize) */
  isProcessing: boolean;
  /** Lỗi voice */
  voiceError: string | null;
  /** Bắt đầu ghi âm → tự transcribe khi dừng → trả về text */
  startRecording: () => Promise<void>;
  /** Dừng ghi âm và transcribe */
  stopRecording: () => Promise<string>;
  /** Phát TTS cho text */
  playTTS: (text: string) => Promise<void>;
  /** Dừng TTS */
  stopTTS: () => void;
}

export function useVoice(): UseVoiceReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const resolveStopRef = useRef<((text: string) => void) | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopTTS();
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    setVoiceError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
        },
      });

      audioChunksRef.current = [];

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm",
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Dừng tất cả tracks để tắt mic
        stream.getTracks().forEach((track) => track.stop());

        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });

        if (audioBlob.size < 100) {
          setVoiceError("Không nhận được audio. Hãy thử lại.");
          resolveStopRef.current?.("");
          resolveStopRef.current = null;
          return;
        }

        setIsProcessing(true);
        try {
          const text = await transcribeAudio(audioBlob);
          resolveStopRef.current?.(text);
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Lỗi nhận dạng giọng nói";
          setVoiceError(msg);
          resolveStopRef.current?.("");
        } finally {
          setIsProcessing(false);
          resolveStopRef.current = null;
        }
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(250); // Collect data every 250ms
      setIsRecording(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Không thể truy cập microphone";
      setVoiceError(msg);
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<string> => {
    return new Promise<string>((resolve) => {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") {
        resolve("");
        return;
      }

      resolveStopRef.current = resolve;
      setIsRecording(false);
      mediaRecorderRef.current.stop();
    });
  }, []);

  const playTTS = useCallback(async (text: string) => {
    setVoiceError(null);

    // Dừng audio đang phát (nếu có)
    stopTTS();

    setIsProcessing(true);
    try {
      const audioBlob = await synthesizeSpeech(text);

      // Cleanup URL cũ
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }

      const url = URL.createObjectURL(audioBlob);
      objectUrlRef.current = url;

      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onplay = () => setIsPlaying(true);
      audio.onended = () => {
        setIsPlaying(false);
        if (objectUrlRef.current) {
          URL.revokeObjectURL(objectUrlRef.current);
          objectUrlRef.current = null;
        }
      };
      audio.onerror = () => {
        setIsPlaying(false);
        setVoiceError("Không thể phát audio");
      };

      setIsProcessing(false);
      await audio.play();
    } catch (err) {
      setIsProcessing(false);
      const msg = err instanceof Error ? err.message : "Lỗi TTS";
      setVoiceError(msg);
    }
  }, []);

  const stopTTS = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setIsPlaying(false);
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  return {
    isRecording,
    isPlaying,
    isProcessing,
    voiceError,
    startRecording,
    stopRecording,
    playTTS,
    stopTTS,
  };
}
