/**
 * PDF export for the direction version of a minute.
 *
 * Pure function — takes a DirectionPreview (from /direction-preview endpoint)
 * and returns a Uint8Array containing the PDF bytes.
 *
 * Sections are renumbered continuously (1, 2, 3...) using the server-provided
 * `position` field. No table of contents, no internal section references.
 * All metadata (Producer, Creator, Title, Author, Subject, Keywords) is
 * explicitly cleared.
 *
 * Unicode support is provided via fontkit. If no font bytes are supplied and
 * the default font fails to load, the function throws rather than producing
 * a PDF with missing characters.
 */

import { PDFDocument, rgb } from 'pdf-lib'

// @pdf-lib/fontkit is CJS, import via dynamic require-style for TS compatibility
// eslint-disable-next-line @typescript-eslint/no-require-imports
const fontkit = require('@pdf-lib/fontkit')

export interface DirectionPreviewSection {
  position: number
  title: string
  content: string  // base64-encoded
  /** Doit valoir exactement 'partage'. Toute autre valeur (ou l'absence de
   *  valeur) fait écarter la section : voir SHARED_MARKER ci-dessous. */
  visibility?: string
}

/** Seule marque autorisée à franchir la frontière vers la direction. */
const SHARED_MARKER = 'partage'

export interface DirectionPreview {
  minute_id: number
  meeting_title: string | null
  validated_by_name: string | null
  validated_at: string | null
  sections: DirectionPreviewSection[]
  generated_at: string
}

const DEFAULT_FONT_URL =
  'https://github.com/google/fonts/raw/main/ofl/notosans/static/NotoSans-Regular.ttf'

const MARGIN = 56
const PAGE_WIDTH = 595  // A4
const PAGE_HEIGHT = 842
const CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN
const FONT_SIZE = 11
const TITLE_FONT_SIZE = 14
const HEADER_FONT_SIZE = 10

function b64Decode(str: string): string {
  const binary = atob(str)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new TextDecoder().decode(bytes)
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('fr-LU', {
      day: 'numeric', month: 'long', year: 'numeric',
    })
  } catch {
    return iso
  }
}

function wrapText(text: string, maxWidth: number, fontSize: number): string[] {
  const avgCharWidth = fontSize * 0.55
  const maxChars = Math.floor(maxWidth / avgCharWidth)
  const lines: string[] = []
  for (const para of text.split('\n')) {
    if (para.length === 0) {
      lines.push('')
      continue
    }
    let remaining = para
    while (remaining.length > 0) {
      if (remaining.length <= maxChars) {
        lines.push(remaining)
        break
      }
      let cut = maxChars
      while (cut > maxChars / 2 && remaining[cut] !== ' ') cut--
      if (cut <= maxChars / 2) cut = maxChars
      lines.push(remaining.slice(0, cut).trimEnd())
      remaining = remaining.slice(cut).trimStart()
    }
  }
  return lines
}

export async function exportDirectionPDF(
  preview: DirectionPreview,
  fontBytes?: Uint8Array,
): Promise<Uint8Array> {
  // Resolve font bytes
  let fontData: Uint8Array
  if (fontBytes) {
    fontData = fontBytes
  } else {
    const resp = await fetch(DEFAULT_FONT_URL)
    if (!resp.ok) {
      throw new Error(
        `Impossible de charger la police Unicode. ` +
        `Le PDF ne peut pas être généré sans prise en charge des accents.`
      )
    }
    fontData = new Uint8Array(await resp.arrayBuffer())
  }

  const pdf = await PDFDocument.create()
  pdf.registerFontkit(fontkit)

  const font = await pdf.embedFont(fontData)

  // ── Metadata purge ────────────────────────────────────────────
  pdf.setTitle('')
  pdf.setAuthor('')
  pdf.setSubject('')
  pdf.setKeywords([])
  pdf.setProducer('')
  pdf.setCreator('')

  // Neutral creation/modification dates
  const neutralDate = new Date('2020-01-01T00:00:00Z')
  pdf.setCreationDate(neutralDate)
  pdf.setModificationDate(neutralDate)

  // ── Content ────────────────────────────────────────────────────
  let page = pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT])
  let y = PAGE_HEIGHT - MARGIN

  function ensureSpace(needed: number) {
    if (y - needed < MARGIN) {
      page = pdf.addPage([PAGE_WIDTH, PAGE_HEIGHT])
      y = PAGE_HEIGHT - MARGIN
    }
  }

  function drawLine(text: string, size: number, opts?: { color?: [number, number, number] }) {
    ensureSpace(size + 4)
    page.drawText(text, {
      x: MARGIN,
      y,
      size,
      font,
      color: rgb(...(opts?.color ?? [0, 0, 0])),
    })
    y -= size + 4
  }

  function drawWrapped(text: string, size: number) {
    const lines = wrapText(text, CONTENT_WIDTH, size)
    for (const line of lines) {
      ensureSpace(size + 3)
      page.drawText(line, {
        x: MARGIN,
        y,
        size,
        font,
        color: rgb(0, 0, 0),
      })
      y -= size + 3
    }
  }

  // ── Header ─────────────────────────────────────────────────────
  drawLine('Procès-verbal — Version destinée à la direction', HEADER_FONT_SIZE, {
    color: [0.5, 0.5, 0.5],
  })
  y -= 6

  if (preview.meeting_title) {
    drawLine(preview.meeting_title, TITLE_FONT_SIZE)
  }

  const headerMeta: string[] = []
  if (preview.validated_at) {
    headerMeta.push(`Réunion du ${formatDate(preview.validated_at)}`)
  }
  if (preview.validated_by_name) {
    headerMeta.push(`Validé par : ${preview.validated_by_name}`)
  }
  if (headerMeta.length > 0) {
    drawLine(headerMeta.join('  ·  '), HEADER_FONT_SIZE, { color: [0.4, 0.4, 0.4] })
  }

  // Horizontal rule
  y -= 8
  ensureSpace(2)
  page.drawLine({
    start: { x: MARGIN, y },
    end: { x: PAGE_WIDTH - MARGIN, y },
    thickness: 1,
    color: rgb(0.7, 0.7, 0.7),
  })
  y -= 16

  // ── Sections ───────────────────────────────────────────────────
  // Filtre FAIL-CLOSED. Le serveur ne projette déjà que les sections
  // partagées, mais l'export ne s'en remet pas à cette garantie : une section
  // qui ne porte pas explicitement la marque 'partage' n'est pas rendue.
  // Deux barrières indépendantes valent mieux qu'une, sur un document qu'on ne
  // peut pas rappeler une fois transmis.
  const sections = preview.sections
    .filter((s) => s.visibility === SHARED_MARKER)
    .sort((a, b) => a.position - b.position)

  let sectionNum = 0
  for (const sec of sections) {
    sectionNum++
    ensureSpace(TITLE_FONT_SIZE + 20)

    // Section title (numbered continuously)
    const titleText = `${sectionNum}. ${sec.title}`
    drawLine(titleText, TITLE_FONT_SIZE)
    y -= 4

    // Section content
    const content = sec.content ? b64Decode(sec.content) : ''
    if (content.trim()) {
      drawWrapped(content, FONT_SIZE)
    } else {
      drawLine('(aucun contenu)', FONT_SIZE, { color: [0.6, 0.6, 0.6] })
    }
    y -= 12
  }

  // ── Footer on each page ────────────────────────────────────────
  const pages = pdf.getPages()
  const totalPages = pages.length
  for (let i = 0; i < pages.length; i++) {
    pages[i].drawText(`${i + 1} / ${totalPages}`, {
      x: PAGE_WIDTH / 2 - 20,
      y: 30,
      size: 8,
      font,
      color: rgb(0.6, 0.6, 0.6),
    })
  }

  // La purge des métadonnées repose sur les setters ci-dessus. Vérifié au
  // niveau des octets par pdfExport.test.ts : la chaîne "pdf-lib" n'apparaît
  // pas dans le fichier produit. Ne pas se fier aux getters de pdf-lib pour
  // le contrôler — getProducer() fabrique une valeur par défaut même quand
  // l'entrée /Producer est absente du document.
  return pdf.save()
}
