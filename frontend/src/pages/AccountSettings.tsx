import { useState, type FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT, LANGS, type Lang } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import MfaSection from '../components/MfaSection'

export default function AccountSettings() {
  const { t, lang, setLang } = useT()
  const { user, setAuth, organization, token } = useAuth()

  const [firstName, setFirstName] = useState(user?.first_name || '')
  const [lastName, setLastName] = useState(user?.last_name || '')
  const [email, setEmail] = useState(user?.email || '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatar_url || '')

  const [oldPass, setOldPass] = useState('')
  const [newPass, setNewPass] = useState('')

  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  async function updateProfile(e: FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/profile', { method: 'PUT', headers, body: JSON.stringify({ first_name: firstName, last_name: lastName, email, avatar_url: avatarUrl || null }) })
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
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <h2>👤 Mon profil</h2>
          <form onSubmit={updateProfile}>
            <div style={{ textAlign:'center', marginBottom:16 }}>
              {avatarUrl ? (
                <img src={avatarUrl} alt="Avatar" style={{ width:80, height:80, borderRadius:'50%', objectFit:'cover', border:'3px solid var(--blue)' }} />
              ) : (
                <div style={{ width:80, height:80, borderRadius:'50%', background:'var(--gray-100)', display:'inline-flex', alignItems:'center', justifyContent:'center', fontSize:'2rem', border:'3px solid var(--gray-300)' }}>
                  {firstName.charAt(0).toUpperCase() || '?'}
                </div>
              )}
            </div>
            <div className="form-group">
              <label>{t('profile.avatar_url')}</label>
              <input value={avatarUrl} onChange={e => setAvatarUrl(e.target.value)} placeholder="https://..." />
              <small style={{ color:'var(--gray-600)' }}>{t('profile.avatar_hint')}</small>
            </div>
            <div className="form-group">
              <label>🌐 Langue</label>
              <select value={lang} onChange={e => setLang(e.target.value as Lang)}
                style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                {LANGS.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>
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
          <h2>🔐 MFA</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>
            Statut : <strong style={{ color: user.totp_enabled ? '#276749' : 'var(--red)' }}>
              {user.totp_enabled ? '✅ Activé' : '❌ Désactivé'}
            </strong>
          </p>
          <MfaSection />
        </div>
      </div>
    </>
  )
}
