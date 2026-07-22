import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import MfaSection from '../components/MfaSection'

export default function AccountSettings() {
  const { user, setAuth, organization, token } = useAuth()
  const navigate = useNavigate()

  // Profile
  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [email, setEmail] = useState(user?.email || '')

  // Password
  const [oldPass, setOldPass] = useState('')
  const [newPass, setNewPass] = useState('')

  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  async function updateProfile(e: FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/profile', { method: 'PUT', headers, body: JSON.stringify({ first_name: firstName, last_name: lastName, email }) })
      if (!res.ok) throw new Error((await res.json()).detail)
      const updated = await res.json()
      if (organization) setAuth(token!, updated, organization)
      setMsg('Profil mis à jour ✅')
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/password', { method: 'PUT', headers, body: JSON.stringify({ old_password: oldPass, new_password: newPass }) })
      if (!res.ok) throw new Error((await res.json()).detail)
      setMsg('Mot de passe changé ✅'); setOldPass(''); setNewPass('')
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  if (!user) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <header className="header"><h1>⚙️ Paramètres du compte</h1><button onClick={() => navigate('/dashboard')}>← Dashboard</button></header>
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <h2>👤 Profil</h2>
          <form onSubmit={updateProfile}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div className="form-group"><label>Prénom</label><input value={firstName} onChange={e => setFirstName(e.target.value)} required /></div>
              <div className="form-group"><label>Nom</label><input value={lastName} onChange={e => setLastName(e.target.value)} required /></div>
            </div>
            <div className="form-group"><label>Email</label><input type="email" value={email} onChange={e => setEmail(e.target.value)} required /></div>
            <button type="submit" className="btn btn-primary" disabled={loading}>Enregistrer</button>
          </form>
        </div>

        <div className="card mb-24">
          <h2>🔑 Mot de passe</h2>
          <form onSubmit={changePassword}>
            <div className="form-group"><label>Ancien mot de passe</label><input type="password" value={oldPass} onChange={e => setOldPass(e.target.value)} required /></div>
            <div className="form-group"><label>Nouveau mot de passe (min. 6)</label><input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} required minLength={6} /></div>
            <button type="submit" className="btn btn-primary" disabled={loading}>Changer le mot de passe</button>
          </form>
        </div>

        <div className="card mb-24">
          <h2>🔐 MFA / Authentification à deux facteurs</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>
            Statut : <strong style={{ color: user.totp_enabled ? '#276749' : 'var(--red)' }}>
              {user.totp_enabled ? '✅ Activé' : '❌ Désactivé'}
            </strong>
          </p>
          <MfaSection />
        </div>

        <p className="text-center"><Link to="/dashboard" className="link">← Retour au dashboard</Link></p>
      </div>
    </>
  )
}
