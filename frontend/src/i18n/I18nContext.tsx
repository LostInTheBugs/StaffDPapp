import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type Lang = 'fr' | 'en' | 'de' | 'pt'

const LANGS: { code: Lang; label: string }[] = [
  { code: 'fr', label: '🇫🇷 Français' },
  { code: 'en', label: '🇬🇧 English' },
  { code: 'de', label: '🇩🇪 Deutsch' },
  { code: 'pt', label: '🇵🇹 Português' },
]

// Chargement paresseux des traductions
const translations: Record<Lang, () => Promise<Record<string, string>>> = {
  fr: () => import('../i18n/fr.json').then(m => m.default),
  en: () => import('../i18n/en.json').then(m => m.default),
  de: () => import('../i18n/de.json').then(m => m.default),
  pt: () => import('../i18n/pt.json').then(m => m.default),
}

interface I18nContextType {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: string, fallback?: string) => string
  langs: typeof LANGS
}

const I18nContext = createContext<I18nContextType>({
  lang: 'fr',
  setLang: () => {},
  t: (k, f) => f || k,
  langs: LANGS,
})

export function I18nProvider({ children, initialLang = 'fr' as Lang }: { children: ReactNode; initialLang?: Lang }) {
  const [lang, setLangState] = useState<Lang>(initialLang)
  const [messages, setMessages] = useState<Record<string, string>>({})

  useEffect(() => {
    translations[lang]().then(setMessages)
  }, [lang])

  const setLang = useCallback(async (l: Lang) => {
    setLangState(l)
    localStorage.setItem('lang', l)
    // Persist to backend
    try {
      const token = localStorage.getItem('token')
      if (token) {
        await fetch('/api/auth/profile', {
          method: 'PUT',
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: l }),
        })
      }
    } catch { /* */ }
  }, [])

  const t = useCallback((key: string, fallback?: string) => {
    return messages[key] || fallback || key
  }, [messages])

  return (
    <I18nContext.Provider value={{ lang, setLang, t, langs: LANGS }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useT() {
  return useContext(I18nContext)
}

export { LANGS }
