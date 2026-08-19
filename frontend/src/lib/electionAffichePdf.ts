import { PDFDocument, StandardFonts, rgb } from 'pdf-lib'

/**
 * Affiche officielle d'annonce des élections (L.413-2).
 * Générée côté client (pdf-lib), à imprimer ou afficher sur le tableau
 * d'affichage virtuel / physique.
 */
export async function generateElectionAffichePdf(opts: {
  orgName: string
  title: string
  electionDate: string
  candidateDeadline: string | null
  seats: number
  notes?: string | null
}): Promise<Uint8Array> {
  const doc = await PDFDocument.create()
  const font = await doc.embedFont(StandardFonts.Helvetica)
  const bold = await doc.embedFont(StandardFonts.HelveticaBold)
  const page = doc.addPage([595, 842]) // A4 portrait

  let y = 800
  const line = (text: string, size = 11, opts: { bold?: boolean; color?: [number, number, number] } = {}) => {
    const f = opts.bold ? bold : font
    page.drawText(text, { x: 48, y, size, font: f, color: opts.color ? rgb(...opts.color) : rgb(0, 0, 0) })
    y -= size + 8
  }

  line('ÉLECTIONS DE LA DÉLÉGATION DU PERSONNEL', 16, { bold: true, color: [0, 0.35, 0.6] })
  line(`Délégation du personnel — ${opts.orgName}`, 12, { bold: true })
  line('Code du travail — Livre IV, Titre I (Art. L.413-1 à L.413-6)', 9, { color: [0.4, 0.4, 0.4] })
  y -= 14

  line(`AVIS D'ÉLECTIONS`, 14, { bold: true })
  line(opts.title, 13, { bold: true })
  y -= 8
  line(`🗳️ Date du scrutin : ${opts.electionDate}`, 12)
  if (opts.candidateDeadline) line(`📥 Date limite de dépôt des candidatures : ${opts.candidateDeadline}`, 12)
  line(`🏛️ Nombre de titulaires à élire : ${opts.seats} (autant de suppléants)`, 12)
  if (opts.notes) line(`📝 ${opts.notes}`, 11)
  y -= 16

  line('ÉLECTEURS (Art. L.413-3)', 11, { bold: true })
  line('• Tous les salariés, sans distinction de nationalité, âgés de 16 ans accomplis', 10)
  line('• Contrat de travail ou apprentissage, ≥ 6 mois d\'occupation au jour de l\'élection', 10)
  y -= 10

  line('ÉLIGIBILITÉ (Art. L.413-4)', 11, { bold: true })
  line('• 18 ans accomplis et ≥ 12 mois d\'ancienneté précédant le 1er jour du mois de l\'affichage', 10)
  line('• Luxembourgeois ou autorisé à travailler', 10)
  line('• Exclus : parents/allies au 4e degré du chef d\'entreprise, gérants, directeurs, responsable du personnel', 10)
  line('• Listes : syndicat représentatif (L.161-4 / L.161-6) ou liste libre ≥ 5 % de l\'effectif (max 100)', 10)
  y -= 10

  line('SCRUTIN (Art. L.413-1)', 11, { bold: true })
  line('• Vote secret à l\'urne, représentation proportionnelle (majorité relative < 100 salariés)', 10)
  line('• Le vote s\'effectue sur la plateforme StaffDPapp (comptes salariés)', 10)
  y -= 10

  line('Le renouvellement de la délégation s\'effectue entre le 1er février et le 31 mars de la 5e année du mandat (Art. L.413-2).', 9, { color: [0.4, 0.4, 0.4] })
  line('Fait le ' + new Date().toLocaleDateString('fr-LU'), 10)
  line('La délégation du personnel', 10, { bold: true })

  // Métadonnées purgées (pattern app)
  doc.setTitle('')
  doc.setAuthor('')
  doc.setSubject('')
  doc.setKeywords([])
  doc.setProducer('')
  doc.setCreator('')

  return doc.save()
}
