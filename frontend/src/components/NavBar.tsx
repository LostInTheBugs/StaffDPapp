import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT, LANGS, type Lang } from '../i18n/I18nContext'

export default function NavBar() {
  const { logout, token } = useAuth()
  const { t, lang, setLang } = useT()
  const [pending, setPending] = useState(0)

  useEffect(() => {
    async function fetchPending() {
      try {
        const res = await fetch('/api/meetings/count/pending', { headers: { Authorization: `Bearer ${token}` } })
        const data = await res.json()
        setPending(data.count || 0)
      } catch { /* */ }
    }
    if (token) fetchPending()
    const interval = setInterval(fetchPending, 30000)
    return () => clearInterval(interval)
  }, [token])

  return (
    <>
      <header className="header">
        <h1>🏢 {t('app.title')}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <select value={lang} onChange={e => setLang(e.target.value as Lang)}
            style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid rgba(255,255,255,.3)', background: 'rgba(255,255,255,.1)', color: '#fff', fontSize: '.8rem', cursor: 'pointer' }}>
            {LANGS.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
          <button onClick={logout}>{t('nav.logout')}</button>
        </div>
      </header>
      <nav style={{ background:'#fff', borderBottom:'1px solid var(--gray-300)', padding:'10px 24px', display:'flex', gap:20, flexWrap:'wrap', alignItems:'center' }}>
        <Link to="/dashboard" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.dashboard')}</Link>
        <Link to="/organigramme" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.organigramme')}</Link>
        <Link to="/meetings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem', position:'relative' }}>
          {t('nav.meetings')}
          {pending > 0 && (
            <span style={{ position:'absolute', top:-8, right:-12, background:'var(--red)', color:'#fff', borderRadius:'50%', width:20, height:20, fontSize:'.7rem', fontWeight:700, display:'inline-flex', alignItems:'center', justifyContent:'center' }}>
              {pending}
            </span>
          )}
        </Link>
        <Link to="/organization" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.organization')}</Link>
        <Link to="/settings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.profile')}</Link>
      </nav>
    </>
  )
}
