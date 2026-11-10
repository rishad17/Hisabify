import { describe, expect, it } from 'vitest'

import { concatChunks, downsample, encodeWav, rms, SILENCE_RMS } from '@/features/voice/wav'

function sine(freq: number, seconds: number, rate: number, amplitude = 0.5): Float32Array {
  const out = new Float32Array(Math.round(seconds * rate))
  for (let i = 0; i < out.length; i++) out[i] = amplitude * Math.sin((2 * Math.PI * freq * i) / rate)
  return out
}

describe('downsample', () => {
  it('48 kHz → 16 kHz keeps duration', () => {
    const out = downsample(sine(220, 1, 48_000), 48_000, 16_000)
    expect(out.length).toBe(16_000)
  })

  it('44.1 kHz → 16 kHz keeps a low tone audible', () => {
    const out = downsample(sine(220, 0.5, 44_100), 44_100, 16_000)
    expect(out.length).toBe(8_000)
    expect(rms(out)).toBeGreaterThan(0.3) // 0.5 amplitude sine → RMS ≈ 0.35
  })

  it('returns input unchanged when already at the target rate', () => {
    const input = sine(220, 0.1, 16_000)
    expect(downsample(input, 16_000)).toBe(input)
  })
})

describe('encodeWav', () => {
  it('writes a valid 16 kHz mono 16-bit header', () => {
    const buffer = encodeWav(new Float32Array(16_000))
    const view = new DataView(buffer)
    const text = (o: number) => String.fromCharCode(...new Uint8Array(buffer, o, 4))
    expect(text(0)).toBe('RIFF')
    expect(text(8)).toBe('WAVE')
    expect(text(36)).toBe('data')
    expect(view.getUint16(22, true)).toBe(1) // mono
    expect(view.getUint32(24, true)).toBe(16_000) // sample rate
    expect(view.getUint16(34, true)).toBe(16) // bits
    expect(buffer.byteLength).toBe(44 + 32_000)
  })

  it('clamps and converts samples', () => {
    const view = new DataView(encodeWav(new Float32Array([0, 1, -1, 2, -2])))
    expect([0, 1, 2, 3, 4].map((i) => view.getInt16(44 + i * 2, true))).toEqual([
      0, 32767, -32768, 32767, -32768,
    ])
  })

  it('60 s fits under the 2.5 MB upload limit', () => {
    expect(encodeWav(new Float32Array(60 * 16_000)).byteLength).toBeLessThan(2_500_000)
  })
})

describe('levels', () => {
  it('detects silence vs speech-level audio', () => {
    expect(rms(new Float32Array(1000))).toBe(0)
    expect(rms(sine(220, 0.1, 16_000, 0.005))).toBeLessThan(SILENCE_RMS)
    expect(rms(sine(220, 0.1, 16_000, 0.2))).toBeGreaterThan(SILENCE_RMS)
  })

  it('concatenates chunks', () => {
    const out = concatChunks([new Float32Array([1, 2]), new Float32Array([3])])
    expect(Array.from(out)).toEqual([1, 2, 3])
  })
})
