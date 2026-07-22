import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function NavBar() {
  const { logout, token } = useAuth()
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
        <h1>🏢 Staff Delegation</h1>
        <button onClick={logout}>Déconnexion</button>
      </header>
      <nav style={{ background:'#fff', borderBottom:'1px solid var(--gray-300)', padding:'10px 24px', display:'flex', gap:20, flexWrap:'wrap', alignItems:'center' }}>
        <Link to="/dashboard" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>📋 Dashboard</Link>
        <Link to="/organigramme" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>👥 Organigramme</Link>
        <Link to="/meetings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem', position:'relative' }}>
          📅 Réunions
          {pending > 0 && (
            <span style={{
              position:'absolute', top:-8, right:-12,
              background:'var(--red)', color:'#fff', borderRadius:'50%',
              width:20, height:20, fontSize:'.7rem', fontWeight:700,
              display:'inline-flex', alignItems:'center', justifyContent:'center',
            }}>
              {pending}
            </span>
          )}
        </Link>
        <Link to="/organization" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>🏢 Mon organisation</Link>
        <Link to="/settings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>👤 Mon profil</Link>
      </nav>
    </>
  )
}
