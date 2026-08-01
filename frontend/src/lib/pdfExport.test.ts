/**
 * The most important test of the module: verify that the direction PDF
 * contains NO internal section content, titles, or metadata leaks.
 *
 * Uses node environment (not jsdom) because pdf-parse requires Buffer.
 *
 * @vitest-environment node
 *
 * Edge cases covered:
 * - Empty internal section
 * - Section flipped from partage→interne after first publication
 * - Unicode characters (é, ü, ë, œ)
 * - Long content forcing page breaks
 * - Internal section text that is a substring of shared section text
 */

import { describe, it, expect, beforeAll } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import { exportDirectionPDF, type DirectionPreview } from '../lib/pdfExport'
import { PDFParse } from 'pdf-parse'
import { PDFDocument } from 'pdf-lib'


/** Réextrait le texte d'un PDF généré. pdf-parse v2 expose une classe,
 *  pas une fonction : c'est bien le PDF produit qui est relu, pas la
 *  structure de données qui a servi à le fabriquer. */
async function extractText(bytes: Uint8Array): Promise<string> {
  const parser = new PDFParse({ data: Buffer.from(bytes) })
  const result = await parser.getText()
  await parser.destroy()
  return result.text
}

function b64Encode(str: string): string {
  const bytes = new TextEncoder().encode(str)
  let binary = ''
  bytes.forEach((b: number) => binary += String.fromCharCode(b))
  return Buffer.from(binary, 'binary').toString('base64')
}

// Police Unicode reelle (TrueType), embarquee localement
let fontBytes: Uint8Array

beforeAll(() => {
  const fontPath = resolve(__dirname, '..', 'assets', 'DejaVuSans.ttf')
  fontBytes = new Uint8Array(readFileSync(fontPath))
})

describe('Direction PDF leak test', () => {

  it('should contain only shared section content, no internal leaks', async () => {
    // Build a preview with intentionally tricky content
    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: 'Réunion du comité — Juillet 2026',
      validated_by_name: 'Marc Weber',
      validated_at: '2026-07-15T10:00:00Z',
      generated_at: '2026-07-15T12:00:00Z',
      sections: [
        { position: 0, title: 'Bilan financier', content: b64Encode("Le budget est équilibré pour l'exercice."), visibility: 'partage' },
        // ── Sections INTERNES délibérément injectées dans l'entrée ──
        // C'est tout l'objet du test : si l'export ne filtrait pas, elles
        // ressortiraient dans le PDF. Les asserts ci-dessous ne sont pas
        // vacuous, ils portent sur des données réellement fournies.
        { position: 0, title: '⚠️ Litige fournisseur', content: b64Encode('Litige confidentiel en cours avec le fournisseur X'), visibility: 'interne' },
        { position: 1, title: 'Stratégie de négociation', content: b64Encode('Négociation salariale — préparation de la contre-offre'), visibility: 'interne' },
        { position: 2, title: 'Décision interne — ne pas diffuser', content: b64Encode("Décision approuvée à l'unanimité concernant le licenciement"), visibility: 'interne' },
        { position: 3, title: 'Ancien partagé — désormais interne', content: b64Encode('Contenu repassé en interne après une première diffusion'), visibility: 'interne' },
        { position: 4, title: 'Section interne vide', content: '', visibility: 'interne' },
        { position: 5, title: 'Sans marque de visibilité', content: b64Encode('Section non marquée : doit être écartée par défaut') },
        { visibility: 'partage', position: 1, title: 'Überblick — Personal a Beweegung', content: b64Encode('Mise à jour sur la mobilité : Müller et Schmit ont été réaffectés à la division Esch-Belval. Nëmme 2 Poste vacants.\n\nLa réorganisation continue avec des résultats positifs.') },
        { visibility: 'partage', position: 2, title: 'Plan stratégique 2026-2027', content: b64Encode('Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n\n'.repeat(30) + 'Fin du plan stratégique.') },
        { visibility: 'partage', position: 3, title: 'Résumé exécutif', content: b64Encode('Décision approuvée.') },
      ],
    }

    // ── Internal sections that MUST NOT appear in the PDF ───────
    const internalSecrets = [
      'Litige confidentiel en cours avec le fournisseur X',
      'Négociation salariale — préparation de la contre-offre',
      "Décision approuvée à l'unanimité concernant le licenciement",  // contains substring of shared text!
    ]
    const internalTitles = [
      '⚠️ Litige fournisseur',
      'Stratégie de négociation',
      'Décision interne — ne pas diffuser',
      'Ancien partagé — désormais interne',
      'Section interne vide',
      'Sans marque de visibilité',
    ]
    const internalSecretsExtra = [
      'Contenu repassé en interne après une première diffusion',
      'Section non marquée : doit être écartée par défaut',
    ]

    // ── Generate the PDF ────────────────────────────────────────
    const pdfBytes = await exportDirectionPDF(preview, fontBytes)

    // Extract text via pdf-parse
    const extractedText = await extractText(pdfBytes)

    // ── Assertions: no internal content leaks ───────────────────
    for (const secret of [...internalSecrets, ...internalSecretsExtra]) {
      expect(extractedText).not.toContain(secret)
    }
    for (const title of internalTitles) {
      expect(extractedText).not.toContain(title)
    }

    // Shared content MUST be present
    expect(extractedText).toContain('Bilan financier')
    expect(extractedText).toContain('budget est équilibré')
    expect(extractedText).toContain('Überblick')
    expect(extractedText).toContain('Müller')
    expect(extractedText).toContain('Résumé exécutif')
    expect(extractedText).toContain('Décision approuvée')

    // ── Continuous numbering (no gaps) ──────────────────────────
    expect(extractedText).toContain('1. Bilan financier')
    expect(extractedText).toContain('2. Überblick')
    expect(extractedText).toContain('3. Plan stratégique')
    expect(extractedText).toContain('4. Résumé exécutif')
    // No "5." or higher should appear (there are only 4 shared sections)
    expect(extractedText).not.toMatch(/^5\. /m)

    // ── No internal content leaks ───────────────────────────────
    expect(extractedText).not.toContain('Litige confidentiel')
    expect(extractedText).not.toContain('Négociation salariale')
    expect(extractedText).not.toContain('fournisseur')
    expect(extractedText).not.toContain('contre-offre')
    expect(extractedText).not.toContain('licenciement')
    expect(extractedText).not.toContain('Ancien partagé')
    expect(extractedText).not.toContain('désormais interne')

    // ── Unicode rendering ───────────────────────────────────────
    expect(extractedText).toContain('é')   // from "équilibré"
    expect(extractedText).toContain('ü')   // from "Überblick"
    expect(extractedText).toContain('ë')   // from "Nëmme"
    // "réaffectés" contains é, already covered

    // ── Purge des métadonnées ───────────────────────────────────
    // On inspecte les OCTETS du PDF, pas les getters de pdf-lib.
    // Piège vérifié empiriquement : reloaded.getProducer() renvoie
    // "pdf-lib (https://github.com/Hopding/pdf-lib)" même quand l'entrée
    // /Producer est absente du fichier — c'est une valeur par défaut
    // fabriquée par le getter. Une assertion sur le getter testerait
    // pdf-lib, pas le document qu'on diffuse.
    const rawPdf = Buffer.from(pdfBytes).toString('latin1')
    expect(rawPdf).not.toContain('pdf-lib')
    expect(rawPdf).not.toContain('Hopding')
    // Aucun horodatage machine : la seule date admise est la date neutre.
    expect(rawPdf).not.toMatch(/D:20(2[1-9]|[3-9]\d)/)
    // Les champs textuels renseignables restent vides.
    const reloaded = await PDFDocument.load(pdfBytes)
    expect(reloaded.getTitle() || '').toBe('')
    expect(reloaded.getAuthor() || '').toBe('')
    expect(reloaded.getSubject() || '').toBe('')
    expect(reloaded.getKeywords() || '').toBe('')
    // Et rien du contenu interne ne doit subsister dans les octets bruts,
    // y compris hors du flux de texte extractible.
    for (const secret of [...internalSecrets, ...internalSecretsExtra]) {
      expect(rawPdf).not.toContain(secret)
    }
    for (const title of internalTitles) {
      expect(rawPdf).not.toContain(title)
    }
    // Numérotation continue : 4 sections partagées, donc 1 à 4 et pas au-delà.
    // Une numérotation à trous trahirait le nombre de sections retirées.
    expect(extractedText).toContain('1. Bilan financier')
    expect(extractedText).toContain('4. Résumé exécutif')
    expect(extractedText).not.toContain('5. ')
  })

  it('should handle empty shared sections gracefully', async () => {
    const preview: DirectionPreview = {
      minute_id: 2,
      meeting_title: 'Réunion test',
      validated_by_name: null,
      validated_at: null,
      generated_at: '2026-01-01T00:00:00Z',
      sections: [
        { position: 0, title: 'Section vide', content: b64Encode(''), visibility: 'partage' },
      ],
    }

    const pdfBytes = await exportDirectionPDF(preview, fontBytes)
    const text = await extractText(pdfBytes)
    expect(text).toContain('Section vide')
    expect(text.length).toBeGreaterThan(0)
  })

  it('rend un PDF sans aucune section si rien n\'est marqué partage', async () => {
    // Barrière fail-closed : même si la projection serveur régressait et
    // renvoyait des sections internes, l'export ne les rendrait pas.
    const preview: DirectionPreview = {
      minute_id: 4,
      meeting_title: 'Réunion test',
      validated_by_name: null,
      validated_at: null,
      generated_at: '2026-01-01T00:00:00Z',
      sections: [
        { position: 0, title: 'Interne A', content: b64Encode('secret A'), visibility: 'interne' },
        { position: 1, title: 'Non marquée', content: b64Encode('secret B') },
      ],
    }

    const pdfBytes = await exportDirectionPDF(preview, fontBytes)
    const text = await extractText(pdfBytes)
    expect(text).not.toContain('Interne A')
    expect(text).not.toContain('secret A')
    expect(text).not.toContain('Non marquée')
    expect(text).not.toContain('secret B')
  })

  it('should throw on invalid font (no silent corrupted PDF)', async () => {
    const preview: DirectionPreview = {
      minute_id: 3,
      meeting_title: 'Test',
      validated_by_name: null,
      validated_at: null,
      generated_at: '2026-01-01T00:00:00Z',
      sections: [
        { position: 0, title: 'Test', content: b64Encode('héllo') },
      ],
    }

    // Empty bytes should fail font embedding
    await expect(
      exportDirectionPDF(preview, new Uint8Array(0))
    ).rejects.toThrow()
  })
})
