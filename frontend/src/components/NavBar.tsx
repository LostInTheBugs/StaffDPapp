import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useVault } from '../hooks/useVault'
import { useT } from '../i18n/I18nContext'
import Footer from './Footer'

export default function NavBar() {
  const { logout, token, user } = useAuth()
  const { status } = useVault()
  const { t } = useT()
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

  // Vault status label and color
  const vaultLabel =
    status === 'unlocked' ? t('vault.status_unlocked') :
    status === 'locked' ? t('vault.status_locked') :
    t('vault.status_disabled')

  const vaultColor =
    status === 'unlocked' ? 'var(--green)' :
    status === 'locked' ? '#dc3545' :
    'var(--gray-500)'

  return (
    <>
      <header className="header">
        <h1>🏢 {t('app.title')}</h1>
        <button onClick={logout}>{t('nav.logout')}</button>
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
        <Link to="/consultations" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.consultations')}</Link>
        <Link to="/workforce-stats" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.stats')}</Link>
        <Link to="/archive" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.archive')}</Link>
        <Link to="/hours" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>⏱️ Mes heures</Link>
        {user?.role === 'admin' && <Link to="/organization" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.organization')}</Link>}
        {user?.role === 'admin' && <Link to="/notifications" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>📧 Notifications</Link>}
        <Link to="/settings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>{t('nav.profile')}</Link>
        {/* Vault status indicator — always visible when authenticated */}
        <span style={{
          marginLeft: 'auto',
          fontSize: '.8rem',
          fontWeight: 600,
          color: vaultColor,
          background: status === 'unlocked' ? '#d4edda' : status === 'locked' ? '#f8d7da' : 'var(--gray-100)',
          padding: '2px 10px',
          borderRadius: 4,
        }}>
          {vaultLabel}
        </span>
      </nav>
      <Footer />
    </>
  )
}
