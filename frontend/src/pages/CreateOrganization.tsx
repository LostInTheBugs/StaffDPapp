import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function CreateOrganization() {
  const [form, setForm] = useState({
    organization_name: '',
    company_name: '',
    admin_full_name: '',
    admin_email: '',
    admin_password: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  function update(field: string, value: string) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (form.admin_password.length < 8) {
      setError('Le mot de passe admin doit contenir au moins 8 caractères')
      return
    }

    setLoading(true)
    try {
      const tokenResp = await api.createOrganization(form)
      localStorage.setItem('token', tokenResp.access_token)
      const dash = await api.getDashboard()
      setAuth(tokenResp.access_token, dash.user, dash.organization)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>🏛️ Créer une délégation du personnel</h2>
        <p className="subtitle">
          Créez l'environnement de votre délégation. Vous serez automatiquement
          administrateur et pourrez inviter les autres membres.
        </p>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>🏢 Votre organisation</legend>
            <div className="form-group">
              <label htmlFor="org_name">Nom de la délégation *</label>
              <input
                id="org_name"
                type="text"
                value={form.organization_name}
                onChange={e => update('organization_name', e.target.value)}
                placeholder="Ex: Délégation du personnel ACME S.A."
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label htmlFor="company_name">Nom officiel de l'entreprise (optionnel)</label>
              <input
                id="company_name"
                type="text"
                value={form.company_name}
                onChange={e => update('company_name', e.target.value)}
                placeholder="Ex: ACME Luxembourg S.A."
              />
            </div>
          </fieldset>

          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>👤 Compte administrateur</legend>
            <div className="form-group">
              <label htmlFor="admin_name">Votre nom complet *</label>
              <input
                id="admin_name"
                type="text"
                value={form.admin_full_name}
                onChange={e => update('admin_full_name', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="admin_email">Votre email *</label>
              <input
                id="admin_email"
                type="email"
                value={form.admin_email}
                onChange={e => update('admin_email', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="admin_password">Mot de passe (min. 8 caractères) *</label>
              <input
                id="admin_password"
                type="password"
                value={form.admin_password}
                onChange={e => update('admin_password', e.target.value)}
                required
                minLength={8}
              />
            </div>
          </fieldset>

          <button type="submit" className="btn btn-gold" disabled={loading}>
            {loading ? <div className="spinner" /> : 'Créer la délégation'}
          </button>
        </form>

        <p className="text-center mt-16">
          <Link to="/" className="link">← Retour à l'accueil</Link>
        </p>
      </div>
    </div>
  )
}
