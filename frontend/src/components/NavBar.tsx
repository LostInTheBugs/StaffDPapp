import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function NavBar() {
  const { logout } = useAuth()

  return (
    <>
      <header className="header">
        <h1>🏢 Staff Delegation</h1>
        <button onClick={logout}>Déconnexion</button>
      </header>
      <nav style={{ background:'#fff', borderBottom:'1px solid var(--gray-300)', padding:'10px 24px', display:'flex', gap:20, flexWrap:'wrap' }}>
        <Link to="/dashboard" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>📋 Dashboard</Link>
        <Link to="/organigramme" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>👥 Organigramme</Link>
        <Link to="/meetings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>📅 Réunions</Link>
        <Link to="/organization" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>🏢 Entreprise</Link>
        <Link to="/settings" style={{ color:'var(--blue)', fontWeight:600, textDecoration:'none', fontSize:'.9rem' }}>⚙️ Paramètres</Link>
      </nav>
    </>
  )
}
