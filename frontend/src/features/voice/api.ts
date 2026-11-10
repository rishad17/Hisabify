import { useMutation } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api'

export type Transcript = {
  text: string
  language: 'bn' | 'en' | 'mixed' | 'unknown'
  provider: string
}

/** Upload a recording; get back editable text. The server never stores the audio. */
export function useTranscribe() {
  return useMutation({
    mutationFn: (audio: Blob) => {
      const form = new FormData()
      form.append('audio', audio, 'voice.wav')
      // No Content-Type header: the browser sets multipart/form-data with the boundary.
      return apiFetch<Transcript>('/api/v1/ai/transcribe', {
        method: 'POST',
        rawBody: form,
        timeoutMs: 45_000,
      })
    },
  })
}
