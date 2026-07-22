import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import CaptchaWidget from '../components/CaptchaWidget'
import * as api from '../api/client'

export default function CreateOrganization() {
  const [form, setForm] = useState({
    organization_name: '', company_name: '', employee_count: 25,
    admin_first_name: '', admin_last_name: '', admin_email: '', admin_password: '',
    admin_delegue_status: 'titulaire', admin_delegue_role: 'president',
  })
  const [captchaId, setCaptchaId] = useState('')
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  function update(field: string, value: string | number) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function getTitulaires(count: number): number {
    const range = api.EMPLOYEE_RANGES.find(r => count >= r.min && count <= r.max)
    if (range) return range.titulaires
    if (count > 5500) return 25 + Math.ceil((count - 5500) / 500)
    return 1
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null)
    if (form.employee_count < 15) { setError("L'effectif minimum est de 15 salariés"); return }
    if (form.admin_password.length < 8) { setError('Le mot de passe admin doit contenir au moins 8 caractères'); return }
    if (!captchaAnswer) { setError('Veuillez résoudre le CAPTCHA'); return }

    setLoading(true)
    try {
      const tokenResp = await api.createOrganization({
        ...form, company_name: form.company_name || undefined,
        captcha_id: captchaId, captcha_answer: captchaAnswer,
        admin_delegue_status: form.admin_delegue_status, admin_delegue_role: form.admin_delegue_role,
      })
      localStorage.setItem('token', tokenResp.access_token)
      const dash = await api.getDashboard()
      setAuth(tokenResp.access_token, dash.user, dash.organization)
      navigate('/dashboard')
    } catch (err: any) { setError(err.message) }
    finally { setLoading(false) }
  }

  const nbTitulaires = getTitulaires(form.employee_count)

  return (
    <div className="container">
      <div className="card">
        <h2>🏛️ Créer une délégation du personnel</h2>
        <p className="subtitle">Créez l'environnement de votre délégation.</p>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>🏢 Organisation</legend>
            <div className="form-group"><label>Nom de la délégation *</label><input value={form.organization_name} onChange={e => update('organization_name', e.target.value)} required autoFocus /></div>
            <div className="form-group"><label>Nom officiel de l'entreprise</label><input value={form.company_name} onChange={e => update('company_name', e.target.value)} /></div>
            <div className="form-group">
              <label>Effectif *</label>
              <select value={form.employee_count} onChange={e => update('employee_count', parseInt(e.target.value))} required
                style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                {api.EMPLOYEE_RANGES.map(r => (
                  <option key={r.min} value={r.min}>{r.min}–{r.max} salariés → {r.titulaires} titulaire{r.titulaires > 1 ? 's' : ''}</option>
                ))}
                <option value={5600}>+ de 5500 salariés</option>
              </select>
              <small style={{ color: 'var(--gray-600)' }}>→ {nbTitulaires} titulaire{nbTitulaires > 1 ? 's' : ''} + {nbTitulaires} suppléant{nbTitulaires > 1 ? 's' : ''} (Art. L.412-1)</small>
            </div>
          </fieldset>
          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>👤 Administrateur</legend>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div className="form-group"><label>Prénom *</label><input value={form.admin_first_name} onChange={e => update('admin_first_name', e.target.value)} required /></div>
              <div className="form-group"><label>Nom *</label><input value={form.admin_last_name} onChange={e => update('admin_last_name', e.target.value)} required /></div>
            </div>
            <div className="form-group"><label>Email *</label><input type="email" value={form.admin_email} onChange={e => update('admin_email', e.target.value)} required /></div>
            <div className="form-group"><label>Mot de passe (min. 8) *</label><input type="password" value={form.admin_password} onChange={e => update('admin_password', e.target.value)} required minLength={8} /></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div className="form-group">
                <label>Statut *</label>
                <select value={form.admin_delegue_status} onChange={e => update('admin_delegue_status', e.target.value)}
                  style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                  {api.DELEGUE_STATUS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Fonction *</label>
                <select value={form.admin_delegue_role} onChange={e => update('admin_delegue_role', e.target.value)}
                  style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                  {api.DELEGUE_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
            </div>
          </fieldset>

          <CaptchaWidget onCaptcha={(id, ans) => { setCaptchaId(id); setCaptchaAnswer(ans) }} />

          <button type="submit" className="btn btn-gold" disabled={loading}>
            {loading ? <div className="spinner" /> : 'Créer la délégation'}
          </button>
        </form>
        <p className="text-center mt-16"><Link to="/" className="link">← Retour</Link></p>
      </div>
    </div>
  )
}
