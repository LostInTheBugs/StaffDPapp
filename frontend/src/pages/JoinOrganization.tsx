import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import CaptchaWidget from '../components/CaptchaWidget'
import * as api from '../api/client'

export default function JoinOrganization() {
  const [form, setForm] = useState({ invitation_code: '', first_name: '', last_name: '', email: '', password: '' })
  const [captchaId, setCaptchaId] = useState('')
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  function update(field: string, value: string) { setForm(prev => ({ ...prev, [field]: value })) }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null)
    if (form.password.length < 6) { setError('Le mot de passe doit contenir au moins 6 caractères'); return }
    if (!captchaAnswer) { setError('Veuillez résoudre le CAPTCHA'); return }

    setLoading(true)
    try {
      const tokenResp = await api.joinOrganization({ ...form, captcha_id: captchaId, captcha_answer: captchaAnswer })
      localStorage.setItem('token', tokenResp.access_token)
      const dash = await api.getDashboard()
      setAuth(tokenResp.access_token, dash.user, dash.organization)
      navigate('/dashboard')
    } catch (err: any) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>✉️ Rejoindre une délégation</h2>
        <p className="subtitle">Saisissez le code d'invitation fourni par l'administrateur.</p>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group"><label>Code d'invitation</label>
            <input value={form.invitation_code} onChange={e => update('invitation_code', e.target.value.toUpperCase())}
              style={{ fontFamily:'monospace', letterSpacing:'2px', textTransform:'uppercase' }} required autoFocus maxLength={20} />
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
            <div className="form-group"><label>Prénom</label><input value={form.first_name} onChange={e => update('first_name', e.target.value)} required /></div>
            <div className="form-group"><label>Nom</label><input value={form.last_name} onChange={e => update('last_name', e.target.value)} required /></div>
          </div>
          <div className="form-group"><label>Email</label><input type="email" value={form.email} onChange={e => update('email', e.target.value)} required /></div>
          <div className="form-group"><label>Mot de passe (min. 6)</label><input type="password" value={form.password} onChange={e => update('password', e.target.value)} required minLength={6} /></div>

          <CaptchaWidget onCaptcha={(id, ans) => { setCaptchaId(id); setCaptchaAnswer(ans) }} />

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <div className="spinner" /> : 'Créer mon compte'}
          </button>
        </form>
        <p className="text-center mt-16"><Link to="/" className="link">← Retour</Link></p>
      </div>
    </div>
  )
}
