import { Info, Loader2, Mic, RotateCcw, Send, Sparkles, Square, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useAIMessage, type AIReply } from '@/features/assistant/api'
import { DraftPreview } from '@/features/assistant/draft-preview'
import { useTranscribe } from '@/features/voice/api'
import { isVoiceSupported, MAX_SECONDS, useVoiceRecorder } from '@/features/voice/use-voice-recorder'

const EXAMPLES = [
  'Ajke 50 taka cha kheyechi',
  '100 rickshaw, 200 lunch, 50 cha',
  'আজকে ১২০ টাকা বাস ভাড়া',
  'Cash theke bKash e 1000 taka',
  'Got 5000 tuition fee',
]

const formatClock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/**
 * Type — or say — what you spent. Voice goes: record → transcribe → EDITABLE text →
 * AI draft → review → save. Nothing is saved without the user's confirmation.
 */
export function QuickEntry() {
  const [text, setText] = useState('')
  const [source, setSource] = useState<'text' | 'voice'>('text')
  const [reply, setReply] = useState<AIReply | null>(null)
  const ai = useAIMessage()
  const transcribe = useTranscribe()
  const recorder = useVoiceRecorder()
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const voiceSupported = isVoiceSupported()

  async function handleRecording(blob: Blob | null) {
    if (!blob) return // silence or cancelled — recorder already set a message if needed
    try {
      const result = await transcribe.mutateAsync(blob)
      setText(result.text)
      setSource('voice')
      requestAnimationFrame(() => inputRef.current?.focus())
    } catch {
      // shown via transcribe.error
    }
  }

  // If the 60 s limit is reached, transcribe what was recorded.
  useEffect(() => {
    recorder.onAutoStop((blob) => void handleRecording(blob))
  })

  async function startRecording() {
    transcribe.reset()
    ai.reset()
    setReply(null)
    await recorder.start()
  }

  async function submit(event?: FormEvent) {
    event?.preventDefault()
    const message = text.trim()
    if (!message || ai.isPending) return
    setReply(null)
    try {
      setReply(await ai.mutateAsync({ text: message, source }))
    } catch {
      // error is shown from ai.error below
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter adds a new line.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      void submit()
    }
  }

  function reset() {
    setReply(null)
    setText('')
    setSource('text')
    ai.reset()
    transcribe.reset()
    inputRef.current?.focus()
  }

  const draft = reply?.kind === 'transaction_draft' ? reply.draft : null
  const recording = recorder.state === 'recording' || recorder.state === 'requesting'
  const busy = ai.isPending || transcribe.isPending

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4 text-primary" aria-hidden />
          Quick entry
        </CardTitle>
        <CardDescription>
          Type or say what you spent or received — English, বাংলা or Banglish. You'll review it before
          anything is saved.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {recording && (
          <RecordingPanel
            requesting={recorder.state === 'requesting'}
            seconds={recorder.seconds}
            level={recorder.level}
            onStop={() => void handleRecording(recorder.stop())}
            onCancel={recorder.cancel}
          />
        )}

        {!draft && !recording && (
          <form onSubmit={submit} className="space-y-2">
            <div className="relative">
              <Textarea
                ref={inputRef}
                value={text}
                onChange={(e) => {
                  setText(e.target.value)
                  if (!e.target.value) setSource('text')
                }}
                onKeyDown={onKeyDown}
                placeholder="e.g. Ajke 100 taka rickshaw vara, 200 taka lunch, ar 50 taka cha"
                maxLength={500}
                rows={2}
                aria-label="Describe your transactions"
                className="min-h-16 resize-none pr-24"
                disabled={busy}
              />
              <div className="absolute right-2 bottom-2 flex gap-1.5">
                {voiceSupported && (
                  <Button
                    type="button"
                    size="icon"
                    variant="outline"
                    className="size-8"
                    onClick={() => void startRecording()}
                    disabled={busy}
                    aria-label="Record voice"
                    title="Record voice (up to 60 seconds)"
                  >
                    <Mic aria-hidden />
                  </Button>
                )}
                <Button
                  type="submit"
                  size="icon"
                  className="size-8"
                  disabled={!text.trim() || busy}
                  aria-label="Send"
                >
                  {ai.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
                </Button>
              </div>
            </div>

            {transcribe.isPending && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Turning your voice into text…
              </p>
            )}
            {ai.isPending && (
              <p className="text-sm text-muted-foreground" role="status">
                Understanding your message…
              </p>
            )}
            {source === 'voice' && text && !busy && !reply && (
              <p className="text-sm text-muted-foreground">
                🎙️ Check the transcript — fix any mistakes — then press Send.
              </p>
            )}
            {!voiceSupported && !text && (
              <p className="text-xs text-muted-foreground">
                Voice input needs a secure (https) page and microphone support in your browser.
              </p>
            )}
            {!busy && !reply && !text && (
              <div className="flex flex-wrap gap-1.5" aria-label="Examples">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => {
                      setText(example)
                      setSource('text')
                      inputRef.current?.focus()
                    }}
                    className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {example}
                  </button>
                ))}
              </div>
            )}
          </form>
        )}

        {(recorder.error || transcribe.isError) && !recording && (
          <Alert variant="destructive">
            <Info aria-hidden />
            <AlertDescription>
              <p>{recorder.error ?? transcribe.error?.message}</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => void startRecording()}>
                  <RotateCcw aria-hidden /> Try again
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    recorder.clearError()
                    transcribe.reset()
                    inputRef.current?.focus()
                  }}
                >
                  Type instead
                </Button>
              </div>
            </AlertDescription>
          </Alert>
        )}

        {ai.isError && (
          <Alert variant="destructive">
            <Info aria-hidden />
            <AlertDescription>{ai.error.message}</AlertDescription>
          </Alert>
        )}

        {reply && reply.kind !== 'transaction_draft' && reply.message && (
          <Alert>
            <Info aria-hidden />
            <AlertDescription>{reply.message}</AlertDescription>
          </Alert>
        )}

        {draft && (
          <>
            <p className="rounded-md bg-muted px-3 py-2 text-sm">
              <span className="text-muted-foreground">{source === 'voice' ? '🎙️ You said: ' : 'You said: '}</span>
              “{text.trim()}”
            </p>
            {reply?.clarifications.map((question) => (
              <Alert key={question}>
                <Info aria-hidden />
                <AlertDescription>{question}</AlertDescription>
              </Alert>
            ))}
            {reply?.message && <p className="text-sm text-muted-foreground">{reply.message}</p>}
            <DraftPreview key={draft.draft_id} draft={draft} onDone={reset} />
          </>
        )}
      </CardContent>
    </Card>
  )
}

function RecordingPanel({
  requesting,
  seconds,
  level,
  onStop,
  onCancel,
}: {
  requesting: boolean
  seconds: number
  level: number
  onStop: () => void
  onCancel: () => void
}) {
  const nearLimit = seconds >= MAX_SECONDS - 10
  return (
    <div className="space-y-3 rounded-lg border border-red-500/40 bg-red-500/5 p-4" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <span className="relative flex size-3" aria-hidden>
          {!requesting && <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-500 opacity-75" />}
          <span className="relative inline-flex size-3 rounded-full bg-red-500" />
        </span>
        <span className="font-medium">
          {requesting ? 'Waiting for microphone permission…' : 'Listening… speak now'}
        </span>
        {!requesting && (
          <span className={`ml-auto text-sm tabular-nums ${nearLimit ? 'text-destructive' : 'text-muted-foreground'}`}>
            {formatClock(seconds)} / {formatClock(MAX_SECONDS)}
          </span>
        )}
      </div>

      {!requesting && (
        <div className="h-2 overflow-hidden rounded-full bg-muted" aria-label="Microphone level">
          <div className="h-full rounded-full bg-red-500 transition-[width] duration-100" style={{ width: `${Math.round(level * 100)}%` }} />
        </div>
      )}

      <div className="flex gap-2">
        <Button onClick={onStop} disabled={requesting} className="flex-1 sm:flex-none">
          <Square className="fill-current" aria-hidden /> Stop
        </Button>
        <Button variant="outline" onClick={onCancel}>
          <X aria-hidden /> Cancel
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Example: “আজকে 50 টাকা চা, 120 টাকা রিকশা আর 200 টাকা lunch”. Audio is not stored.
      </p>
    </div>
  )
}
