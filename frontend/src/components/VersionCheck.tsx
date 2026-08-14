import { useEffect, useState } from 'react'

/** Version locale (synchronisée avec le footer / les releases). */
const LOCAL_VERSION = '2026.08.011'

function cmpVersions(a: string, b: string): number {
  const pa = a.replace(/^v/, '').split(/[.\-]/).map(n => parseInt(n) || 0)
  const pb = b.replace(/^v/, '').split(/[.\-]/).map(n => parseInt(n) || 0)
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] || 0
    const y = pb[i] || 0
    if (x !== y) return x - y
  }
  return 0
}

/**
 * Bandeau « nouvelle version disponible » — le SEUL lien avec GitHub.
 * Interroge l'API publique des releases (aucun token) et compare avec la
 * version locale. Silencieux si à jour, si offline ou si l'API échoue.
 */
export default function VersionCheck() {
  const [latest, setLatest] = useState<string | undefined>(undefined)
  const [url, setUrl] = useState<string | undefined>(undefined)

  useEffect(() => {
    let cancelled = false
    fetch('https://api.github.com/repos/LostInTheBugs/StaffDPapp/releases/latest')
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (cancelled || !data?.tag_name) return
        if (cmpVersions(data.tag_name, LOCAL_VERSION) > 0) {
          setLatest(data.tag_name)
          setUrl(data.html_url || `https://github.com/LostInTheBugs/StaffDPapp/releases/tag/${data.tag_name}`)
        }
      })
      .catch(() => { /* offline ou API bloquée : silencieux */ })
    return () => { cancelled = true }
  }, [])

  if (!latest) return null

  return (
    <div style={{
      background: '#2b6cb0', color: '#fff', textAlign: 'center',
      padding: '8px 16px', fontSize: '.85rem', fontWeight: 600,
    }}>
      🚀 Une nouvelle version <strong>{latest}</strong> de StaffDPapp est disponible —{' '}
      <a href={url} target="_blank" rel="noreferrer" style={{ color: '#fff', textDecoration: 'underline' }}>
        voir les nouveautés
      </a>
    </div>
  )
}
