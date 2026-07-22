import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function JoinOrganization() {
  const [form, setForm] = useState({
    invitation_code: '',
    full_name: '',
    email: '',
    password: '',
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

    if (form.password.length < 6) {
      setError('Le mot de passe doit contenir au moins 6 caractères')
      return
    }

    setLoading(true)
    try {
      const tokenResp = await api.joinOrganization(form)
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
        <h2>✉️ Rejoindre une délégation</h2>
        <p className="subtitle">
          Saisissez le code d'invitation fourni par l'administrateur de votre délégation.
        </p>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="code">Code d'invitation</label>
            <input
              id="code"
              type="text"
              value={form.invitation_code}
              onChange={e => update('invitation_code', e.target.value.toUpperCase())}
              placeholder="Ex: A1B2C3D4"
              required
              autoFocus
              maxLength={20}
              style={{ fontFamily: 'monospace', letterSpacing: '2px', textTransform: 'uppercase' }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="name">Nom complet</label>
            <input
              id="name"
              type="text"
              value={form.full_name}
              onChange={e => update('full_name', e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={e => update('email', e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Mot de passe (min. 6 caractères)</label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={e => update('password', e.target.value)}
              required
              minLength={6}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <div className="spinner" /> : 'Créer mon compte'}
          </button>
        </form>

        <p className="text-center mt-16">
          <Link to="/" className="link">← Retour à l'accueil</Link>
        </p>
      </div>
    </div>
  )
}
