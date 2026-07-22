import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function CreateOrganization() {
  const [form, setForm] = useState({
    organization_name: '',
    company_name: '',
    employee_count: 25,
    admin_first_name: '',
    admin_last_name: '',
    admin_email: '',
    admin_password: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

  function update(field: string, value: string | number) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const getTitulaires = (count: number): number => {
    const range = api.EMPLOYEE_RANGES.find(r => count >= r.min && count <= r.max)
    if (range) return range.titulaires
    if (count > 5500) return 25 + Math.ceil((count - 5500) / 500)
    return 1
  }

  const nbTitulaires = getTitulaires(form.employee_count)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)

    if (form.employee_count < 15) {
      setError("L'effectif minimum est de 15 salariés")
      return
    }
    if (form.admin_password.length < 8) {
      setError('Le mot de passe admin doit contenir au moins 8 caractères')
      return
    }

    setLoading(true)
    try {
      const tokenResp = await api.createOrganization({
        organization_name: form.organization_name,
        company_name: form.company_name || undefined,
        employee_count: form.employee_count,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
        admin_first_name: form.admin_first_name,
        admin_last_name: form.admin_last_name,
      })
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
          administrateur et Président.
        </p>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>🏢 Votre organisation</legend>
            <div className="form-group">
              <label htmlFor="org_name">Nom de la délégation *</label>
              <input id="org_name" type="text" value={form.organization_name}
                onChange={e => update('organization_name', e.target.value)}
                placeholder="Ex: Délégation du personnel ACME S.A." required autoFocus />
            </div>
            <div className="form-group">
              <label htmlFor="company_name">Nom officiel de l'entreprise (optionnel)</label>
              <input id="company_name" type="text" value={form.company_name}
                onChange={e => update('company_name', e.target.value)}
                placeholder="Ex: ACME Luxembourg S.A." />
            </div>
            <div className="form-group">
              <label htmlFor="employee_count">Effectif de l'entreprise *</label>
              <input id="employee_count" type="number" min={15} value={form.employee_count}
                onChange={e => update('employee_count', parseInt(e.target.value) || 0)} required />
              <small style={{ color: 'var(--gray-600)' }}>
                → {nbTitulaires} titulaire{nbTitulaires > 1 ? 's' : ''} requis (Art. L.412-1)
                {nbTitulaires > 0 && <> + {nbTitulaires} suppléant{nbTitulaires > 1 ? 's' : ''}</>}
              </small>
            </div>
          </fieldset>

          <fieldset style={{ border: '1px solid var(--gray-300)', borderRadius: 'var(--radius)', padding: '20px 16px', marginBottom: 24 }}>
            <legend style={{ fontWeight: 700, color: 'var(--blue)', padding: '0 8px' }}>👤 Administrateur</legend>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div className="form-group">
                <label htmlFor="admin_first_name">Prénom *</label>
                <input id="admin_first_name" type="text" value={form.admin_first_name}
                  onChange={e => update('admin_first_name', e.target.value)} required />
              </div>
              <div className="form-group">
                <label htmlFor="admin_last_name">Nom *</label>
                <input id="admin_last_name" type="text" value={form.admin_last_name}
                  onChange={e => update('admin_last_name', e.target.value)} required />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="admin_email">Email *</label>
              <input id="admin_email" type="email" value={form.admin_email}
                onChange={e => update('admin_email', e.target.value)} required />
            </div>
            <div className="form-group">
              <label htmlFor="admin_password">Mot de passe (min. 8 caractères) *</label>
              <input id="admin_password" type="password" value={form.admin_password}
                onChange={e => update('admin_password', e.target.value)} required minLength={8} />
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
