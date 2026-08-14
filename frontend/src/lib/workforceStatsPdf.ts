/**
 * PDF export for the semiannual workforce statistics (Art. L.414-3).
 *
 * Pure function — takes the statistics rows + organisation name and returns
 * a Uint8Array containing the PDF bytes. Same conventions as pdfExport.ts:
 * embedded Unicode font, metadata purged, no external dependency.
 */

import { PDFDocument, rgb } from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'
import defaultFontUrl from '../assets/DejaVuSans.ttf?url'
import type { WorkforceStat } from '../api/client'

const PAGE_WIDTH = 595.28 // A4 portrait (points)
const PAGE_HEIGHT = 841.89
const MARGIN = 56

export async function exportWorkforceStatsPDF(
  rows: WorkforceStat[],
  orgName: string,
  fontBytes?: Uint8Array,
): Promise<Uint8Array> {
  let fontData: Uint8Array
  if (fontBytes) {
    fontData = fontBytes
  } else {
    const resp = await fetch(defaultFontUrl)
    if (!resp.ok) {
      throw new Error('Impossible de charger la police Unicode embarquée — export PDF impossible.')
    }
    fontData = new Uint8Array(await resp.arrayBuffer())
  }

  const pdf = await PDFDocument.create()
  pdf.registerFontkit(fontkit)
  const font = await pdf.embedFont(fontData)

  pdf.setTitle('')
  pdf.setAuthor('')
  pdf.setSubject('')
  pdf.setKeywords([])
  pdf.setProducer('')
  pdf.setCreator('')
  const neutralDate = new Date('2020-01-01T00:00:00Z')
  pdf.setCreationDate(neutralDate)
  pdf.setModificationDate(neutralDate)

  const page = pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT])
  let y = PAGE_HEIGHT - MARGIN

  // ── En-tête ──
  page.drawText('Statistiques de l\'effectif par sexe', { x: MARGIN, y, size: 17, font, color: rgb(0.1, 0.1, 0.1) })
  y -= 24
  page.drawText(orgName, { x: MARGIN, y, size: 11, font, color: rgb(0.25, 0.25, 0.25) })
  y -= 16
  page.drawText(`Rapport semestriel — Art. L.414-3 du Code du travail (généré le ${new Date().toLocaleDateString('fr-LU')})`, {
    x: MARGIN, y, size: 9, font, color: rgb(0.45, 0.45, 0.45),
  })
  y -= 26

  // ── Tableau ──
  const colX = [MARGIN, MARGIN + 130, MARGIN + 210, MARGIN + 290, MARGIN + 370, MARGIN + 440]
  const headers = ['Semestre', 'Hommes', 'Femmes', 'Total', '% Hommes', '% Femmes']

  // Header row
  page.drawRectangle({
    x: MARGIN - 6, y: y - 14, width: colX[5] - MARGIN + 12, height: 22,
    color: rgb(0.92, 0.93, 0.95),
  })
  headers.forEach((h, i) => {
    page.drawText(h, { x: colX[i], y: y - 8, size: 9, font, color: rgb(0.2, 0.2, 0.2) })
  })
  y -= 34

  if (rows.length === 0) {
    page.drawText('Aucun rapport publié.', { x: MARGIN, y, size: 10, font, color: rgb(0.4, 0.4, 0.4) })
  } else {
    const sorted = [...rows].sort((a, b) => b.semester.localeCompare(a.semester))
    let totalM = 0
    let totalF = 0
    for (const r of sorted) {
      const [year, half] = r.semester.split('-')
      const label = `${year} — S${half}`
      const pctM = r.total ? Math.round((r.male_count / r.total) * 100) : 0
      const pctF = r.total ? Math.round((r.female_count / r.total) * 100) : 0
      page.drawText(label, { x: colX[0], y, size: 10, font })
      page.drawText(String(r.male_count), { x: colX[1], y, size: 10, font })
      page.drawText(String(r.female_count), { x: colX[2], y, size: 10, font })
      page.drawText(String(r.total), { x: colX[3], y, size: 10, font })
      page.drawText(`${pctM} %`, { x: colX[4], y, size: 10, font })
      page.drawText(`${pctF} %`, { x: colX[5], y, size: 10, font })
      // Ligne de séparation légère
      page.drawLine({
        start: { x: MARGIN - 6, y: y - 4 },
        end: { x: colX[5] + 6, y: y - 4 },
        thickness: 0.4, color: rgb(0.85, 0.85, 0.85),
      })
      y -= 18
      totalM += r.male_count
      totalF += r.female_count
    }

    // Ligne cumulée
    y -= 4
    page.drawRectangle({
      x: MARGIN - 6, y: y - 6, width: colX[5] - MARGIN + 12, height: 18,
      color: rgb(0.95, 0.96, 0.98),
    })
    const grandTotal = totalM + totalF
    page.drawText('Total', { x: colX[0], y: y - 1, size: 10, font })
    page.drawText(String(totalM), { x: colX[1], y: y - 1, size: 10, font })
    page.drawText(String(totalF), { x: colX[2], y: y - 1, size: 10, font })
    page.drawText(String(grandTotal), { x: colX[3], y: y - 1, size: 10, font })
    page.drawText(`${grandTotal ? Math.round((totalM / grandTotal) * 100) : 0} %`, { x: colX[4], y: y - 1, size: 10, font })
    page.drawText(`${grandTotal ? Math.round((totalF / grandTotal) * 100) : 0} %`, { x: colX[5], y: y - 1, size: 10, font })
    y -= 34
  }

  // ── Pied de page légal ──
  page.drawText(
    'Statistiques établies conformément à l\'article L.414-3 du Code du travail luxembourgeois :',
    { x: MARGIN, y, size: 8.5, font, color: rgb(0.4, 0.4, 0.4) },
  )
  y -= 13
  page.drawText(
    '« L\'employeur établit, chaque semestre, les statistiques de l\'effectif ventilées par sexe et les communique à la délégation du personnel. »',
    { x: MARGIN, y, size: 8.5, font, color: rgb(0.4, 0.4, 0.4) },
  )

  return pdf.save()
}
