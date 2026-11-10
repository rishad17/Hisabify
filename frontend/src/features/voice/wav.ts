/**
 * Pure audio helpers (no browser APIs) — unit-tested in wav.test.ts.
 *
 * Browsers record at 44.1/48 kHz in float32. Speech recognition only needs 16 kHz mono,
 * and 16-bit PCM WAV is the one format every speech service accepts. 60 s ≈ 1.9 MB.
 */

export const TARGET_SAMPLE_RATE = 16_000

/** Average-downsample float samples from `inRate` to `outRate` (outRate ≤ inRate). */
export function downsample(input: Float32Array, inRate: number, outRate = TARGET_SAMPLE_RATE): Float32Array {
  if (outRate >= inRate) return input
  const ratio = inRate / outRate
  const length = Math.floor(input.length / ratio)
  const output = new Float32Array(length)
  for (let i = 0; i < length; i++) {
    // Averaging the samples that map to one output sample acts as a simple low-pass
    // filter, which avoids most aliasing artefacts.
    const start = Math.floor(i * ratio)
    const end = Math.min(input.length, Math.floor((i + 1) * ratio))
    let sum = 0
    for (let j = start; j < end; j++) sum += input[j]
    output[i] = sum / Math.max(1, end - start)
  }
  return output
}

/** Encode mono float samples (−1..1) as a 16-bit PCM WAV file. */
export function encodeWav(samples: Float32Array, sampleRate = TARGET_SAMPLE_RATE): ArrayBuffer {
  const bytesPerSample = 2
  const dataSize = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  const writeString = (offset: number, text: string) => {
    for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true) // byte rate
  view.setUint16(32, bytesPerSample, true) // block align
  view.setUint16(34, 16, true) // bits per sample
  writeString(36, 'data')
  view.setUint32(40, dataSize, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
  }
  return buffer
}

/** Root-mean-square level of a chunk (0 = silence, ~0.1–0.5 = normal speech). */
export function rms(samples: Float32Array): number {
  if (samples.length === 0) return 0
  let sum = 0
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i]
  return Math.sqrt(sum / samples.length)
}

/**
 * Below this loudness the recording is treated as silence and NOT uploaded.
 * Mirrors the backend check (RMS 300 on the 16-bit scale ≈ 0.009) — silence must never
 * reach the AI, which can hallucinate words from nothing.
 */
export const SILENCE_RMS = 0.01

export function concatChunks(chunks: Float32Array[]): Float32Array {
  const total = chunks.reduce((n, c) => n + c.length, 0)
  const out = new Float32Array(total)
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.length
  }
  return out
}
