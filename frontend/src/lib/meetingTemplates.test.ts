import { describe, expect, it } from 'vitest'
import { MEETING_TEMPLATES, templatePointTexts } from './meetingTemplates'
import fr from '../i18n/fr.json'

const t = (k: string, fb?: string) => (fr as Record<string, string>)[k] ?? fb ?? k

describe('meetingTemplates', () => {
  it('defines the 4 statutory templates', () => {
    expect(MEETING_TEMPLATES.map(tpl => tpl.id)).toEqual(['ordinaire', 'direction', 'securite', 'egalite'])
  })

  it('every template has points, at least one mandatory point, and unique keys', () => {
    for (const tpl of MEETING_TEMPLATES) {
      expect(tpl.points.length).toBeGreaterThan(0)
      expect(tpl.points.some(p => p.mandatory)).toBe(true)
      const keys = tpl.points.map(p => p.key)
      expect(new Set(keys).size).toBe(keys.length)
    }
  })

  it('all template names and point keys exist in fr.json', () => {
    const frKeys = Object.keys(fr)
    for (const tpl of MEETING_TEMPLATES) {
      expect(frKeys).toContain(tpl.nameKey)
      for (const p of tpl.points) expect(frKeys).toContain(p.key)
    }
  })

  it('resolves localized point texts carrying the legal article reference', () => {
    const texts = templatePointTexts(MEETING_TEMPLATES[0], t)
    expect(texts.length).toBe(MEETING_TEMPLATES[0].points.length)
    expect(texts[0]).toContain('L.416-5')
    expect(texts.every(x => x.length > 5)).toBe(true)
  })

  it('direction template includes all ordinary-meeting recurring points', () => {
    const ord = MEETING_TEMPLATES.find(x => x.id === 'ordinaire')!
    const dir = MEETING_TEMPLATES.find(x => x.id === 'direction')!
    for (const p of ord.points) expect(dir.points).toContainEqual(p)
  })

  it('sécurité/santé and égalité templates carry the designated-delegate article refs', () => {
    const securite = MEETING_TEMPLATES.find(x => x.id === 'securite')!
    const egalite = MEETING_TEMPLATES.find(x => x.id === 'egalite')!
    expect(templatePointTexts(securite, t).some(x => x.includes('L.414-14'))).toBe(true)
    expect(templatePointTexts(egalite, t).some(x => x.includes('L.414-15'))).toBe(true)
  })
})
