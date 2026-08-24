// Meeting agenda templates — Luxembourg Code du travail, Livre IV, Titre I
// (verified against Legilux, applicable 10.03.2026 — see skill reference
// luxembourg-legal-rules.md). Point texts are i18n keys; the legal article
// reference is part of the localized text so it is stored with the meeting point.

export interface TemplatePoint {
  key: string
  mandatory: boolean
}

export interface MeetingTemplate {
  id: 'ordinaire' | 'direction' | 'securite' | 'egalite'
  nameKey: string
  points: TemplatePoint[]
}

const ORDINAIRE_POINTS: TemplatePoint[] = [
  // Lecture et approbation du PV — L.416-5
  { key: 'templates.ordinaire.p1', mandatory: true },
  // Réclamations des salariés — L.414-2
  { key: 'templates.ordinaire.p2', mandatory: true },
  // Questions d'1/3 des membres — L.416-2
  { key: 'templates.ordinaire.p3', mandatory: true },
  // Suivi des décisions
  { key: 'templates.ordinaire.p4', mandatory: false },
  // Crédit d'heures — L.415-5
  { key: 'templates.ordinaire.p5', mandatory: false },
  // Affichage — L.414-16
  { key: 'templates.ordinaire.p6', mandatory: false },
  // Prochaine réunion — L.415-6
  { key: 'templates.ordinaire.p7', mandatory: false },
]

export const MEETING_TEMPLATES: MeetingTemplate[] = [
  {
    id: 'ordinaire',
    nameKey: 'templates.name_ordinaire',
    points: ORDINAIRE_POINTS,
  },
  {
    id: 'direction',
    nameKey: 'templates.name_direction',
    points: [
      ...ORDINAIRE_POINTS,
      // Vie de l'entreprise — L.414-3
      { key: 'templates.direction.p1', mandatory: true },
      // Stats semestrielles par sexe — L.414-3
      { key: 'templates.direction.p2', mandatory: true },
      // Réponse motivée aux consultations — L.414-1
      { key: 'templates.direction.p3', mandatory: true },
      // Modifications importantes — L.414-3
      { key: 'templates.direction.p4', mandatory: true },
      // Rapport éco-financier ≥150 — L.414-5
      { key: 'templates.direction.p5', mandatory: true },
      // Réponses aux réclamations — L.414-2
      { key: 'templates.direction.p6', mandatory: false },
    ],
  },
  {
    id: 'securite',
    nameKey: 'templates.name_securite',
    points: [
      // Tournées de contrôle — L.414-14
      { key: 'templates.securite.p1', mandatory: true },
      // Registre spécial — L.414-14
      { key: 'templates.securite.p2', mandatory: true },
      // Consultation 11 domaines — L.414-14
      { key: 'templates.securite.p3', mandatory: true },
      // Accidents / incidents
      { key: 'templates.securite.p4', mandatory: true },
      // Signalements des salariés
      { key: 'templates.securite.p5', mandatory: false },
      // Saisine ITM d'urgence — L.414-14
      { key: 'templates.securite.p6', mandatory: false },
      // Formation 40h + 10h — L.415-9
      { key: 'templates.securite.p7', mandatory: false },
      // Prochaines tournées / prévention
      { key: 'templates.securite.p8', mandatory: false },
    ],
  },
  {
    id: 'egalite',
    nameKey: 'templates.name_egalite',
    points: [
      // Réclamations discrimination — L.414-15
      { key: 'templates.egalite.p1', mandatory: true },
      // Plan d'égalité — L.414-15
      { key: 'templates.egalite.p2', mandatory: true },
      // Stats semestrielles par sexe — L.414-3
      { key: 'templates.egalite.p3', mandatory: true },
      // Avis préalable temps partiel — L.414-15
      { key: 'templates.egalite.p4', mandatory: true },
      // Égalité salariale
      { key: 'templates.egalite.p5', mandatory: false },
      // Sensibilisation / convocation annuelle par sexe — L.414-15
      { key: 'templates.egalite.p6', mandatory: false },
      // Formation 2 demi-journées — L.415-9
      { key: 'templates.egalite.p7', mandatory: false },
      // Prochaines actions
      { key: 'templates.egalite.p8', mandatory: false },
    ],
  },
]

/** Resolve a template's points to localized texts (ready to store as MeetingPoint descriptions). */
export function templatePointTexts(
  template: MeetingTemplate,
  t: (key: string, fallback?: string) => string,
): string[] {
  return template.points.map(p => t(p.key, p.key))
}
