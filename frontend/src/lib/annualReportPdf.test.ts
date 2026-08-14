import { describe, expect, it, beforeAll } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { PDFDocument } from 'pdf-lib'
import { PDFParse } from 'pdf-parse'
import { exportAnnualReportPDF } from './annualReportPdf'
import type { AnnualReportData } from '../api/client'

const fontBytes = new Uint8Array(readFileSync(resolve(__dirname, '../assets/DejaVuSans.ttf')))

const DATA: AnnualReportData = {
  year: 2026,
  organization: {
    name: 'Demo SARL',
    company: 'Demo Industries',
    employee_count: 120,
    weekly_credit_hours: 10,
    equality_monthly_credit: 10,
  },
  workforce: [
    { semester: '2026-1', male_count: 68, female_count: 55, total: 123 },
    { semester: '2026-2', male_count: 70, female_count: 56, total: 126 },
  ],
  hours: {
    total: 42.5,
    by_category: { reunion: 20, tournee: 12.5, administratif: 10 },
    by_user: [
      { user_id: 1, name: 'Sophie Muller', email: 'sophie@demo.lu', delegue_status: 'titulaire', total_hours: 25 },
      { user_id: 2, name: 'Marc Weber', email: 'marc@demo.lu', delegue_status: 'titulaire', total_hours: 17.5 },
    ],
  },
  meetings: { total: 7, with_direction: 3 },
  consultations: { total: 2, answered: 1 },
  designates: [
    {
      user_id: 2, name: 'Marc Weber', email: 'marc@demo.lu', delegue_status: 'titulaire',
      roles: ['securite_sante'], total_hours: 12.5, hours_by_category: { tournee: 12.5 },
    },
    {
      user_id: 3, name: 'Tom Wagner', email: 'tom@demo.lu', delegue_status: 'titulaire',
      roles: ['egalite'], total_hours: 8, hours_by_category: { reunion: 8 },
    },
  ],
}

let bytes: Uint8Array
let doc: PDFDocument

beforeAll(async () => {
  bytes = await exportAnnualReportPDF(DATA, fontBytes)
  doc = await PDFDocument.load(bytes)
})

describe('annual report PDF', () => {
  it('produces a valid PDF', () => {
    expect(bytes.length).toBeGreaterThan(1000)
    expect(doc.getPageCount()).toBeGreaterThanOrEqual(1)
  })

  it('contains all sections', async () => {
    const parser = new PDFParse({ data: bytes as unknown as Buffer })
    const result = await parser.getText()
    const text = result.text
    expect(text).toContain('Rapport d\'activité annuel')
    expect(text).toContain('Année 2026')
    expect(text).toContain('Effectif par sexe')
    expect(text).toContain('2026-1')
    expect(text).toContain('Heures de délégation')
    expect(text).toContain('42.5 h')
    expect(text).toContain('Réunions')
    expect(text).toContain('Consultations')
    expect(text).toContain('Délégués désignés')
    expect(text).toContain('Marc Weber')
    expect(text).toContain('sécurité/santé')
    expect(text).toContain('égalité')
  })

  it('handles empty years', async () => {
    const empty: AnnualReportData = {
      ...DATA,
      workforce: [],
      hours: { total: 0, by_category: {}, by_user: [] },
      meetings: { total: 0, with_direction: 0 },
      consultations: { total: 0, answered: 0 },
      designates: [],
    }
    const b = await exportAnnualReportPDF(empty, fontBytes)
    const d = await PDFDocument.load(b)
    expect(d.getPageCount()).toBe(1)
  })

  it('purges metadata (bytes check)', () => {
    const rawPdf = Buffer.from(bytes).toString('latin1')
    expect(rawPdf).not.toContain('pdf-lib')
    expect(rawPdf).not.toContain('Hopding')
  })
})
