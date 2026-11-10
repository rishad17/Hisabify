import { Info, Loader2, Send, Sparkles } from 'lucide-react'
import { useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useAIMessage, type AIReply } from '@/features/assistant/api'
import { DraftPreview } from '@/features/assistant/draft-preview'

const EXAMPLES = [
  'Ajke 50 taka cha kheyechi',
  '100 rickshaw, 200 lunch, 50 cha',
  'আজকে ১২০ টাকা বাস ভাড়া',
  'Cash theke bKash e 1000 taka',
  'Got 5000 tuition fee',
]

/**
 * "Type what you spent" box. The AI turns the text into a DRAFT; the user reviews it in
 * DraftPreview and only then saves. Voice input (Phase 5) will feed the same textarea.
 */
export function QuickEntry() {
  const [text, setText] = useState('')
  const [reply, setReply] = useState<AIReply | null>(null)
  const ai = useAIMessage()
  const inputRef = useRef<HTMLTextAreaElement>(null)

  async function submit(event?: FormEvent) {
    event?.preventDefault()
    const message = text.trim()
    if (!message || ai.isPending) return
    setReply(null)
    try {
      setReply(await ai.mutateAsync({ text: message }))
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
    ai.reset()
    inputRef.current?.focus()
  }

  const draft = reply?.kind === 'transaction_draft' ? reply.draft : null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4 text-primary" aria-hidden />
          Quick entry
        </CardTitle>
        <CardDescription>
          Type what you spent or received — English, বাংলা or Banglish. You'll review it before anything is
          saved.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {!draft && (
          <form onSubmit={submit} className="space-y-2">
            <div className="relative">
              <Textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="e.g. Ajke 100 taka rickshaw vara, 200 taka lunch, ar 50 taka cha"
                maxLength={500}
                rows={2}
                aria-label="Describe your transactions"
                className="min-h-16 resize-none pr-12"
                disabled={ai.isPending}
              />
              <Button
                type="submit"
                size="icon"
                className="absolute right-2 bottom-2 size-8"
                disabled={!text.trim() || ai.isPending}
                aria-label="Send"
              >
                {ai.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Send aria-hidden />}
              </Button>
            </div>
            {ai.isPending && (
              <p className="text-sm text-muted-foreground" role="status">
                Understanding your message…
              </p>
            )}
            {!ai.isPending && !reply && !text && (
              <div className="flex flex-wrap gap-1.5" aria-label="Examples">
                {EXAMPLES.map((example) => (
                  <button
                    key={example}
                    type="button"
                    onClick={() => {
                      setText(example)
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
              <span className="text-muted-foreground">You said: </span>“{text.trim()}”
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
