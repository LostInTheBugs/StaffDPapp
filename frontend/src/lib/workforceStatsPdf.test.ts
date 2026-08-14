import { describe, expect, it, beforeAll } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { PDFDocument } from 'pdf-lib'
import { PDFParse } from 'pdf-parse'
import { exportWorkforceStatsPDF } from './workforceStatsPdf'
import type { WorkforceStat } from '../api/client'

// Police Unicode réelle (TrueType), embarquée localement — comme pdfExport.test.ts
let fontBytes: Uint8Array

beforeAll(() => {
  const fontPath = resolve(__dirname, '..', 'assets', 'DejaVuSans.ttf')
  fontBytes = new Uint8Array(readFileSync(fontPath))
})

const ROWS: WorkforceStat[] = [
  {
    id: 1, organization_id: 1, semester: '2026-1',
    male_count: 68, female_count: 55, total: 123, created_at: null,
  },
  {
    id: 2, organization_id: 1, semester: '2025-2',
    male_count: 70, female_count: 50, total: 120, created_at: null,
  },
]

async function extractText(bytes: Uint8Array): Promise<string> {
  const parser = new PDFParse({ data: bytes as unknown as Buffer })
  const result = await parser.getText()
  return result.text
}

let bytes: Uint8Array
let doc: PDFDocument

beforeAll(async () => {
  bytes = await exportWorkforceStatsPDF(ROWS, 'Demo SARL', fontBytes)
  doc = await PDFDocument.load(bytes)
})

describe('exportWorkforceStatsPDF', () => {
  it('produces a valid PDF with one A4 page', () => {
    expect(bytes[0]).toBe(0x25) // '%'
    expect(bytes[1]).toBe(0x50) // 'P'
    expect(bytes[2]).toBe(0x44) // 'D'
    expect(bytes[3]).toBe(0x46) // 'F'
    const pages = doc.getPages()
    expect(pages.length).toBe(1)
    const { width, height } = pages[0].getSize()
    expect(width).toBeCloseTo(595.28, 0)
    expect(height).toBeCloseTo(841.89, 0)
  })

  it('contains the semesters and totals', async () => {
    const text = await extractText(bytes)
    expect(text).toContain('2026 — S1')
    expect(text).toContain('2025 — S2')
    expect(text).toContain('123')
    expect(text).toContain('68')
    expect(text).toContain('55')
    expect(text).toContain('Total')
    expect(text).toContain('L.414-3')
    expect(text).toContain('Demo SARL')
  })

  it('purges metadata', () => {
    // Vérification sur les OCTETS (le getter getProducer() de pdf-lib renvoie
    // une valeur par défaut même quand /Producer est absent — piège connu).
    const rawPdf = Buffer.from(bytes).toString('latin1')
    expect(rawPdf).not.toContain('pdf-lib')
    expect(rawPdf).not.toContain('Hopding')
    expect(doc.getTitle() || '').toBe('')
    expect(doc.getAuthor() || '').toBe('')
    expect(doc.getSubject() || '').toBe('')
    expect(doc.getCreator() || '').toBe('')
  })

  it('handles empty history', async () => {
    const empty = await exportWorkforceStatsPDF([], 'Demo SARL', fontBytes)
    const d = await PDFDocument.load(empty)
    expect(d.getPageCount()).toBe(1)
  })
})
