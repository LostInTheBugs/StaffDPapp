import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function EditOrganization() {
  const { organization, setAuth, token } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    name: organization?.name || '',
    company_name: organization?.company_name || '',
    employee_count: organization?.employee_count || 15,
  })
  const [error, setError] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function update(field: string, value: string | number) {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  function getTitulaires(count: number): number {
    const range = api.EMPLOYEE_RANGES.find(r => count >= r.min && count <= r.max)
    if (range) return range.titulaires
    if (count > 5500) return 25 + Math.ceil((count - 5500) / 500)
    return 1
  }

  const nbTitulaires = getTitulaires(form.employee_count)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null); setMsg(null)
    if (form.employee_count < 15) { setError("L'effectif minimum est de 15 salariés"); return }
    setLoading(true)
    try {
      const updated = await api.updateOrganization({
        name: form.name || undefined,
        company_name: form.company_name || undefined,
        employee_count: form.employee_count,
      })
      // Refresh auth context
      if (organization && token) {
        setAuth(token, { ...organization, ...updated } as any, updated)
      }
      setMsg('Entreprise mise à jour ✅')
    } catch (err: any) { setError(err.message) }
    finally { setLoading(false) }
  }

  if (!organization) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <header className="header">
        <h1>🏢 {organization.name}</h1>
        <button onClick={() => navigate('/dashboard')}>← Dashboard</button>
      </header>
      <div className="dashboard">
        <div className="card mb-24">
          <h2>🏢 Mon entreprise</h2>
          <p className="subtitle">Modifiez les informations de votre délégation.</p>
          {msg && <div className="success-msg">{msg}</div>}
          {error && <div className="error-msg">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="form-group"><label>Nom de la délégation</label><input value={form.name} onChange={e => update('name', e.target.value)} /></div>
            <div className="form-group"><label>Nom officiel de l'entreprise</label><input value={form.company_name} onChange={e => update('company_name', e.target.value)} /></div>
            <div className="form-group">
              <label>Effectif</label>
              <input type="number" min={15} value={form.employee_count} onChange={e => update('employee_count', parseInt(e.target.value) || 0)} />
              <small style={{ color: 'var(--gray-600)' }}>→ {nbTitulaires} titulaire{nbTitulaires > 1 ? 's' : ''} + {nbTitulaires} suppléant{nbTitulaires > 1 ? 's' : ''} (Art. L.412-1)</small>
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <div className="spinner" /> : 'Enregistrer'}
            </button>
          </form>
        </div>
        <p className="text-center"><Link to="/dashboard" className="link">← Retour au dashboard</Link></p>
      </div>
    </>
  )
}
