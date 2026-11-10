import { useCallback, useEffect, useRef, useState } from 'react'

import {
  concatChunks,
  downsample,
  encodeWav,
  rms,
  SILENCE_RMS,
  TARGET_SAMPLE_RATE,
} from '@/features/voice/wav'

export const MAX_SECONDS = 60

export type RecorderState = 'idle' | 'requesting' | 'recording' | 'error'

type WindowWithWebkit = Window & { webkitAudioContext?: typeof AudioContext }

/** Voice needs a secure page (https or localhost), mic access and the Web Audio API. */
export function isVoiceSupported(): boolean {
  if (typeof window === 'undefined') return false
  return Boolean(
    window.isSecureContext &&
      typeof navigator.mediaDevices?.getUserMedia === 'function' &&
      (window.AudioContext || (window as WindowWithWebkit).webkitAudioContext),
  )
}

function micErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : ''
  switch (name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Microphone access was blocked. Allow it from the 🔒 icon in the address bar, then try again.'
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No microphone found. Plug one in or type instead.'
    case 'NotReadableError':
      return 'Your microphone is being used by another app. Close it and try again.'
    default:
      return 'Could not start the microphone. You can type instead.'
  }
}

/**
 * Records mono audio and returns a 16 kHz WAV Blob.
 *
 * Uses ScriptProcessorNode: deprecated, but it still works in every browser (including
 * older Safari), whereas MediaRecorder produces different formats per browser.
 * Recording only happens between start() and stop() — never in the background.
 */
export function useVoiceRecorder() {
  const [state, setState] = useState<RecorderState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [level, setLevel] = useState(0)

  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const chunksRef = useRef<Float32Array[]>([])
  const peakRef = useRef(0)
  const timerRef = useRef<number | null>(null)
  const startedAtRef = useRef(0)
  /** Receives the audio if recording hits MAX_SECONDS without the user pressing stop. */
  const autoStoppedRef = useRef<((blob: Blob | null) => void) | null>(null)

  const cleanup = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current)
    timerRef.current = null
    processorRef.current?.disconnect()
    processorRef.current = null
    streamRef.current?.getTracks().forEach((t) => t.stop()) // turns the mic indicator off
    streamRef.current = null
    void ctxRef.current?.close().catch(() => {})
    ctxRef.current = null
    setLevel(0)
  }, [])

  const finish = useCallback((): Blob | null => {
    const ctx = ctxRef.current
    const rate = ctx?.sampleRate ?? 48_000
    const chunks = chunksRef.current
    const peak = peakRef.current
    chunksRef.current = []
    cleanup()
    setState('idle')

    if (chunks.length === 0) return null
    if (peak < SILENCE_RMS) {
      setError("I couldn't hear anything. Check your mic and speak a little louder.")
      setState('error')
      return null
    }
    const samples = downsample(concatChunks(chunks), rate, TARGET_SAMPLE_RATE)
    return new Blob([encodeWav(samples, TARGET_SAMPLE_RATE)], { type: 'audio/wav' })
  }, [cleanup])

  /** Stop recording and get the WAV (null if nothing usable was recorded). */
  const stop = useCallback((): Blob | null => (ctxRef.current ? finish() : null), [finish])

  const start = useCallback(async () => {
    setError(null)
    setSeconds(0)
    if (!isVoiceSupported()) {
      setError('Voice input isn\'t available in this browser. You can type instead.')
      setState('error')
      return
    }
    setState('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      const Ctx = window.AudioContext || (window as WindowWithWebkit).webkitAudioContext!
      const ctx = new Ctx()
      await ctx.resume() // Safari starts contexts suspended
      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)

      chunksRef.current = []
      peakRef.current = 0
      processor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(input)) // copy: the buffer is reused
        const current = rms(input)
        peakRef.current = Math.max(peakRef.current, current)
        setLevel(Math.min(1, current * 6))
      }
      source.connect(processor)
      processor.connect(ctx.destination) // required for onaudioprocess to fire (outputs silence)

      ctxRef.current = ctx
      streamRef.current = stream
      processorRef.current = processor
      startedAtRef.current = Date.now()
      setState('recording')

      timerRef.current = window.setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000)
        setSeconds(elapsed)
        if (elapsed >= MAX_SECONDS) autoStoppedRef.current?.(finish())
      }, 250)
    } catch (err) {
      cleanup()
      setError(micErrorMessage(err))
      setState('error')
    }
  }, [cleanup, finish])

  const cancel = useCallback(() => {
    chunksRef.current = []
    cleanup()
    setState('idle')
    setError(null)
  }, [cleanup])

  // Never leave the microphone on if the component unmounts mid-recording.
  useEffect(() => cleanup, [cleanup])

  return {
    state,
    error,
    seconds,
    level,
    start,
    stop,
    cancel,
    clearError: () => {
      setError(null)
      setState('idle')
    },
    onAutoStop: (handler: (blob: Blob | null) => void) => {
      autoStoppedRef.current = handler
    },
  }
}
