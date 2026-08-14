import { describe, expect, it } from 'vitest'
import {
  generateDEK, generateRecoveryKey, formatRecoveryKey,
  wrapDEKWithRecoveryKey, unwrapDEKWithRecoveryKey, WrongPasswordError,
} from './vault'

describe('recovery key', () => {
  it('formats a recovery key as XXXX-XXXX-XXXX-XXXX', () => {
    const k = generateRecoveryKey()
    expect(k).toMatch(/^[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}$/)
  })

  it('normalizes messy input (lowercase, spaces, dashes)', () => {
    expect(formatRecoveryKey('a1b2-c3d4 e5f6 a7b8')).toBe('A1B2-C3D4-E5F6-A7B8')
    expect(formatRecoveryKey('a1b2c3d4e5f6a7b8')).toBe('A1B2-C3D4-E5F6-A7B8')
    expect(formatRecoveryKey('a1b2-c3d4-e5f6-a7b8-extra')).toBe('A1B2-C3D4-E5F6-A7B8')
  })

  it('wrap → unwrap roundtrip recovers the DEK', async () => {
    const dek = generateDEK()
    const key = generateRecoveryKey()
    const env = await wrapDEKWithRecoveryKey(dek, key)
    expect(env.wrapped.length).toBe(48) // 32 + 16 GCM tag
    expect(env.salt.length).toBe(16)
    expect(env.nonce.length).toBe(12)

    const recovered = await unwrapDEKWithRecoveryKey(env.wrapped, key, env.salt, env.params, env.nonce)
    expect(recovered).toEqual(dek)
  })

  it('wrong key throws WrongPasswordError', async () => {
    const dek = generateDEK()
    const env = await wrapDEKWithRecoveryKey(dek, generateRecoveryKey())
    await expect(
      unwrapDEKWithRecoveryKey(env.wrapped, generateRecoveryKey(), env.salt, env.params, env.nonce),
    ).rejects.toThrow(WrongPasswordError)
  })

  it('two wraps with the same key produce different envelopes', async () => {
    const dek = generateDEK()
    const key = generateRecoveryKey()
    const a = await wrapDEKWithRecoveryKey(dek, key)
    const b = await wrapDEKWithRecoveryKey(dek, key)
    expect(a.wrapped).not.toEqual(b.wrapped)
    expect(a.salt).not.toEqual(b.salt)
  })

  it('each generated key is unique', () => {
    const keys = new Set(Array.from({ length: 20 }, () => generateRecoveryKey()))
    expect(keys.size).toBe(20)
  })
})
