import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import CaptchaWidget from '../components/CaptchaWidget'
import * as api from '../api/client'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [captchaId, setCaptchaId] = useState('')
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // MFA step
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [totpCode, setTotpCode] = useState('')

  const { setAuth } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null)

    if (!mfaToken) {
      // Step 1: password + captcha
      setLoading(true)
      try {
        const resp = await api.login(email, password, captchaId || undefined, captchaAnswer || undefined)
        if (resp.mfa_required && resp.mfa_token) {
          setMfaToken(resp.mfa_token)
        } else {
          localStorage.setItem('token', resp.access_token)
          const dash = await api.getDashboard()
          setAuth(resp.access_token, dash.user, dash.organization)
          navigate('/dashboard')
        }
      } catch (err: any) { setError(err.message) }
      finally { setLoading(false) }
    } else {
      // Step 2: TOTP
      if (totpCode.length < 6) { setError('Code TOTP invalide'); return }
      setLoading(true)
      try {
        const resp = await api.mfaLogin(mfaToken, totpCode)
        localStorage.setItem('token', resp.access_token)
        const dash = await api.getDashboard()
        setAuth(resp.access_token, dash.user, dash.organization)
        navigate('/dashboard')
      } catch (err: any) { setError(err.message) }
      finally { setLoading(false) }
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>🔑 {mfaToken ? 'Vérification MFA' : 'Connexion'}</h2>

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {!mfaToken ? (
            <>
              <div className="form-group"><label htmlFor="email">Email</label>
                <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
              </div>
              <div className="form-group"><label htmlFor="password">Mot de passe</label>
                <input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
              </div>
              <CaptchaWidget onCaptcha={(id, ans) => { setCaptchaId(id); setCaptchaAnswer(ans) }} />
            </>
          ) : (
            <div className="form-group">
              <label htmlFor="totp">Code d'authentification (6 chiffres)</label>
              <input id="totp" type="text" inputMode="numeric" autoComplete="one-time-code"
                value={totpCode} onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                required autoFocus maxLength={6}
                style={{ fontFamily:'monospace', fontSize:'1.4rem', textAlign:'center', letterSpacing:'4px' }} />
            </div>
          )}

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? <div className="spinner" /> : mfaToken ? 'Vérifier' : 'Se connecter'}
          </button>
        </form>

        {mfaToken && (
          <p className="text-center mt-16">
            <button onClick={() => { setMfaToken(null); setTotpCode(''); setError(null) }}
              className="link" style={{ background:'none', border:'none', cursor:'pointer' }}>
              ← Retour
            </button>
          </p>
        )}
        {!mfaToken && (
          <p className="text-center mt-16">
            <Link to="/" className="link">← Retour à l'accueil</Link>
          </p>
        )}
      </div>
    </div>
  )
}
