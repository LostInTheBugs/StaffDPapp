import { describe, expect, it } from 'vitest'
import { semesterLabel } from './semester'

describe('semesterLabel', () => {
  it('formats S1 and S2 semesters', () => {
    expect(semesterLabel('2026-1')).toBe('2026 — S1')
    expect(semesterLabel('2026-2')).toBe('2026 — S2')
  })
})
