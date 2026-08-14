/**
 * PDF export for the annual activity report (rapport d'activité annuel).
 *
 * Aggregates the delegation's yearly activity into one A4 document:
 * 1. Workforce by sex (Art. L.414-3)
 * 2. Delegation hours (Art. L.415-5)
 * 3. Meetings (Art. L.415-6)
 * 4. Consultations (Art. L.414-3)
 * 5. Designated delegates — sécurité/santé (L.414-14), égalité (L.414-15)
 *
 * Pure function; same conventions as workforceStatsPdf.ts: embedded Unicode
 * font, purged metadata, no external dependency.
 */

import { PDFDocument, rgb } from 'pdf-lib'
import fontkit from '@pdf-lib/fontkit'
import defaultFontUrl from '../assets/DejaVuSans.ttf?url'
import type { AnnualReportData } from '../api/client'

const PAGE_WIDTH = 595.28 // A4 portrait (points)
const PAGE_HEIGHT = 841.89
const MARGIN = 56
const FOOTER_Y = 46

const GRAY_DARK = rgb(0.1, 0.1, 0.1)
const GRAY_MID = rgb(0.25, 0.25, 0.25)
const GRAY_LIGHT = rgb(0.45, 0.45, 0.45)
const HEADER_BG = rgb(0.92, 0.93, 0.95)
const ROW_ALT = rgb(0.97, 0.97, 0.98)
const BLUE = rgb(0.12, 0.31, 0.55)

const CATEGORY_LABELS: Record<string, string> = {
  reunion: 'Réunions',
  formation: 'Formations',
  tournee: 'Tournées de contrôle',
  administratif: 'Administratif',
  autre: 'Autre',
}

const ROLE_LABELS: Record<string, string> = {
  securite_sante: 'Délégué sécurité/santé (L.414-14)',
  egalite: 'Délégué à l\'égalité (L.414-15)',
}

export async function exportAnnualReportPDF(
  data: AnnualReportData,
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

  const ctx = { pdf, font, page, y }

  function newPageIfNeeded(needed: number) {
    if (ctx.y - needed < FOOTER_Y + 30) {
      ctx.page = ctx.pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT])
      ctx.y = PAGE_HEIGHT - MARGIN
    }
  }

  function sectionTitle(text: string) {
    newPageIfNeeded(48)
    ctx.y -= 18
    ctx.page.drawText(text, { x: MARGIN, y: ctx.y, size: 12.5, font, color: BLUE })
    ctx.y -= 16
    ctx.page.drawRectangle({
      x: MARGIN, y: ctx.y - 1, width: PAGE_WIDTH - 2 * MARGIN, height: 0.6,
      color: rgb(0.75, 0.78, 0.82),
    })
    ctx.y -= 12
  }

  function row(text: string, value: string, indent = 0) {
    ctx.page.drawText(text, { x: MARGIN + indent, y: ctx.y, size: 9.5, font, color: GRAY_DARK })
    ctx.page.drawText(value, { x: PAGE_WIDTH - MARGIN - 90, y: ctx.y, size: 9.5, font, color: GRAY_DARK })
    ctx.y -= 15
  }

  function table(header: string[], rowsData: string[][], widths: number[]) {
    newPageIfNeeded(30 + rowsData.length * 18)
    // Header
    ctx.page.drawRectangle({
      x: MARGIN - 6, y: ctx.y - 14, width: PAGE_WIDTH - 2 * MARGIN + 12, height: 20,
      color: HEADER_BG,
    })
    let x = MARGIN
    header.forEach((h, i) => {
      ctx.page.drawText(h, { x: x + 4, y: ctx.y - 10, size: 8.5, font, color: GRAY_DARK })
      x += widths[i]
    })
    ctx.y -= 22
    // Rows
    rowsData.forEach((cells, ri) => {
      if (ctx.y < FOOTER_Y + 40) {
        ctx.page = ctx.pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT])
        ctx.y = PAGE_HEIGHT - MARGIN
        ctx.page.drawRectangle({
          x: MARGIN - 6, y: ctx.y - 14, width: PAGE_WIDTH - 2 * MARGIN + 12, height: 20,
          color: HEADER_BG,
        })
        let hx = MARGIN
        header.forEach((h, i) => {
          ctx.page.drawText(h, { x: hx + 4, y: ctx.y - 10, size: 8.5, font, color: GRAY_DARK })
          hx += widths[i]
        })
        ctx.y -= 22
      }
      if (ri % 2 === 1) {
        ctx.page.drawRectangle({
          x: MARGIN - 6, y: ctx.y - 13, width: PAGE_WIDTH - 2 * MARGIN + 12, height: 18,
          color: ROW_ALT,
        })
      }
      let cx = MARGIN
      cells.forEach((c, i) => {
        ctx.page.drawText(c, { x: cx + 4, y: ctx.y - 9.5, size: 8.5, font, color: GRAY_DARK })
        cx += widths[i]
      })
      ctx.y -= 19
    })
    ctx.y -= 6
  }

  function footnote(text: string) {
    newPageIfNeeded(24)
    ctx.y -= 8
    ctx.page.drawText(text, { x: MARGIN, y: ctx.y, size: 7.5, font, color: GRAY_LIGHT })
    ctx.y -= 12
  }

  // ── En-tête ──
  const org = data.organization
  page.drawText('Rapport d\'activité annuel de la délégation du personnel', { x: MARGIN, y, size: 16, font, color: GRAY_DARK })
  y -= 24
  page.drawText(`${org.name} — ${org.company || ''}`.trim(), { x: MARGIN, y, size: 11, font, color: GRAY_MID })
  y -= 16
  page.drawText(`Année ${data.year} · ${org.employee_count} salariés · Crédit hebdomadaire ${org.weekly_credit_hours ?? '—'} h (L.415-5) · Généré le ${new Date().toLocaleDateString('fr-LU')}`, {
    x: MARGIN, y, size: 9, font, color: GRAY_LIGHT,
  })
  y -= 24
  ctx.y = y

  // ── 1. Effectif par sexe ──
  sectionTitle('1. Effectif par sexe (Art. L.414-3)')
  if (data.workforce.length === 0) {
    footnote('Aucune statistique semestrielle publiée pour cette année.')
  } else {
    const rows = data.workforce.map((w) => {
      const pct = w.total > 0 ? ((w.male_count / w.total) * 100).toFixed(0) : '0'
      return [
        w.semester,
        String(w.male_count),
        String(w.female_count),
        String(w.total),
        `${pct} %`,
      ]
    })
    table(['Semestre', 'Hommes', 'Femmes', 'Total', '% Hommes'], rows, [120, 100, 100, 100, 100])
  }

  // ── 2. Heures de délégation ──
  sectionTitle('2. Heures de délégation (Art. L.415-5)')
  row('Total des heures déclarées', `${data.hours.total} h`)
  Object.entries(data.hours.by_category).forEach(([cat, h]) => {
    row(`  · ${CATEGORY_LABELS[cat] || cat}`, `${h} h`)
  })
  ctx.y -= 6
  if (data.hours.by_user.length > 0) {
    const top = data.hours.by_user.slice(0, 8)
    const rows = top.map((u) => [u.name, String(u.total_hours)])
    table(['Membre', 'Heures'], rows, [300, 120])
    if (data.hours.by_user.length > 8) {
      footnote(`+ ${data.hours.by_user.length - 8} autres membres`)
    }
  }

  // ── 3. Réunions ──
  sectionTitle('3. Réunions (Art. L.415-6)')
  row('Réunions tenues', `${data.meetings.total}`)
  row('  · avec la direction', `${data.meetings.with_direction}`)

  // ── 4. Consultations ──
  sectionTitle('4. Consultations de l\'effectif (Art. L.414-3)')
  row('Consultations lancées', `${data.consultations.total}`)
  row('  · avec réponse de la direction', `${data.consultations.answered}`)

  // ── 5. Délégués désignés ──
  sectionTitle('5. Délégués désignés (L.414-14 sécurité/santé · L.414-15 égalité)')
  if (data.designates.length === 0) {
    footnote('Aucun délégué désigné (sécurité/santé ou égalité) pour cette année.')
  } else {
    const rows = data.designates.map((d) => [
      d.name,
      d.roles.map((r) => ROLE_LABELS[r] || r).join(' + '),
      String(d.total_hours),
    ])
    table(['Membre', 'Désignation', 'Heures déclarées'], rows, [170, 240, 100])
    footnote(`Crédit mensuel délégué égalité : ${org.equality_monthly_credit} h (effectif ${org.employee_count} salariés) · Congé-formation sécurité/santé : 40 h/mandat (+10 h premier mandat).`)
  }

  // ── Pied légal ──
  footnote('Document établi par la délégation du personnel à titre informatif — ne constitue pas un conseil juridique.')
  footnote('Art. L.414-3 · L.414-14 · L.414-15 · L.415-5 · L.415-6 du Code du travail luxembourgeois.')

  return pdf.save()
}
