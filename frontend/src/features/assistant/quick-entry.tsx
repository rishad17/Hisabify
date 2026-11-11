import { Info, Loader2, MessageSquareText, Mic, RotateCcw, Send, Sparkles, Square, X } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useAIMessage, type AIReply, type HistoryTurn, type ToolUse } from '@/features/assistant/api'
import { DataCards } from '@/features/assistant/data-cards'
import { MiniMarkdown } from '@/features/assistant/mini-markdown'
import { DraftPreview } from '@/features/assistant/draft-preview'
import { useTranscribe } from '@/features/voice/api'
import { isVoiceSupported, MAX_SECONDS, useVoiceRecorder } from '@/features/voice/use-voice-recorder'

const EXAMPLES = [
  'Ajke 50 taka cha kheyechi',
  '100 rickshaw, 200 lunch, 50 cha',
  'আজকে ১২০ টাকা বাস ভাড়া',
  'Cash theke bKash e 1000 taka',
  'Ei mash e koto khoroch holo?',
  'Can I buy a 2500 taka keyboard?',
]

type ThreadMessage = { role: 'user' | 'assistant'; text: string; tools?: ToolUse[] }

const formatClock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

/**
 * Type — or say — what you spent. Voice goes: record → transcribe → EDITABLE text →
 * AI draft → review → save. Nothing is saved without the user's confirmation.
 */
export function QuickEntry() {
  const [text, setText] = useState('')
  const [source, setSource] = useState<'text' | 'voice'>('text')
  const [reply, setReply] = useState<AIReply | null>(null)
  // Q&A conversation (answers only; recording drafts use the preview below).
  const [thread, setThread] = useState<ThreadMessage[]>([])
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
    const history: HistoryTurn[] = thread.slice(-6).map(({ role, text }) => ({ role, text }))
    try {
      const r = await ai.mutateAsync({ text: message, source, history })
      if (r.kind === 'answer' && r.answer) {
        // Questions become a conversation; the box clears for a follow-up.
        setThread((t) => [...t, { role: 'user', text: message }, { role: 'assistant', text: r.answer!, tools: r.tools_used }])
        setText('')
        setSource('text')
      } else {
        setReply(r)
      }
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

  useEffect(() => {
    function onKey(e: globalThis.KeyboardEvent) {
      if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target as HTMLElement | null
      if (t && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))) return
      if (!inputRef.current) return
      e.preventDefault()
      inputRef.current.focus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-primary">
            <Sparkles className="size-4" aria-hidden />
          </span>
          Ask or record
          <kbd
            className="ml-auto hidden h-5 items-center rounded border bg-muted px-1.5 font-sans text-[11px] font-medium text-muted-foreground lg:inline-flex"
            title="Press / to start typing"
          >
            /
          </kbd>
        </CardTitle>
        <CardDescription>
          Type or say what you spent — or ask about your money — in English, বাংলা or Banglish. Nothing is saved
          until you confirm it.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {thread.length > 0 && (
          <div className="space-y-3" aria-live="polite">
            {thread.map((m, i) =>
              m.role === 'user' ? (
                <p key={i} className="ml-auto w-fit max-w-[85%] animate-in rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-primary-foreground duration-200 fade-in-0 slide-in-from-bottom-1">
                  {m.text}
                </p>
              ) : (
                <div key={i} className="animate-in space-y-2 duration-300 fade-in-0 slide-in-from-bottom-1">
                  <div className="flex gap-2">
                    <MessageSquareText className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                    <MiniMarkdown text={m.text} />
                  </div>
                  {m.tools && m.tools.length > 0 && <div className="pl-6"><DataCards tools={m.tools} /></div>}
                </div>
              ),
            )}
            <div className="flex justify-end">
              <Button variant="ghost" size="sm" onClick={() => setThread([])}>
                Clear conversation
              </Button>
            </div>
          </div>
        )}
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
                placeholder={thread.length ? 'Ask a follow-up… e.g. “and last month?”' : 'e.g. Ajke 100 taka rickshaw vara, 200 lunch — or “How much did I spend this month?”'}
                maxLength={500}
                rows={2}
                aria-label="Describe your transactions"
                className="min-h-[72px] resize-none pr-24"
                disabled={busy}
              />
              <div className="absolute right-2 bottom-2 flex gap-1.5">
                {voiceSupported && (
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="outline"
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
                  size="icon-sm"
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
              <p className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
                <span className="flex gap-1" aria-hidden>
                  <span className="size-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                  <span className="size-1.5 animate-bounce rounded-full bg-primary" />
                </span>
                Thinking…
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
            {!busy && !reply && !text && thread.length === 0 && (
              <div
                className="-mx-5 flex gap-1.5 overflow-x-auto px-5 pb-0.5 scrollbar-none sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0"
                aria-label="Examples"
              >
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => {
                      setText(example)
                      setSource('text')
                      inputRef.current?.focus()
                    }}
                    className="shrink-0 rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors duration-150 hover:border-primary/40 hover:bg-accent hover:text-accent-foreground"
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
