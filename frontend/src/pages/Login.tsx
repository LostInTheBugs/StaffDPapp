import { useState, useEffect, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import CaptchaWidget from '../components/CaptchaWidget'
import VersionCheck from '../components/VersionCheck'
import * as api from '../api/client'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [captchaId, setCaptchaId] = useState('')
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // Organisation (slug) — affiche le logo de l'entreprise avant connexion
  const [orgSlug, setOrgSlug] = useState(() => localStorage.getItem('org_slug') || '')
  const [publicOrg, setPublicOrg] = useState<{ name: string; company_name: string | null; logo_data: string | null } | null>(null)

  // MFA step
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [totpCode, setTotpCode] = useState('')

  const { setAuth } = useAuth()
  const { t } = useT()
  const navigate = useNavigate()

  async function lookupOrg(slug: string) {
    const s = slug.trim().toLowerCase()
    if (!s) { setPublicOrg(null); return }
    try {
      const org = await api.getPublicOrg(s)
      setPublicOrg(org)
      localStorage.setItem('org_slug', s)
    } catch {
      setPublicOrg(null)
    }
  }

  // Rejoue le lookup au montage quand un slug est déjà mémorisé
  useEffect(() => {
    const saved = localStorage.getItem('org_slug')
    if (saved) lookupOrg(saved)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null)

    if (!mfaToken) {
      // Step 1: password + captcha
      setLoading(true)
      try {
        const resp = await api.login(email, password, captchaId, captchaAnswer)
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
    <>
      <VersionCheck />
      <div className="container">
      <div className="card">
        <h2>🔑 {mfaToken ? 'Vérification MFA' : 'Connexion'}</h2>

        {!mfaToken && publicOrg && (
          <div style={{ textAlign: 'center', marginBottom: 14 }}>
            {publicOrg.logo_data
              ? <img src={publicOrg.logo_data} alt="logo" style={{ maxHeight: 64, maxWidth: 220, objectFit: 'contain' }} />
              : <div style={{ fontSize: '2.2rem' }}>🏢</div>}
            <div style={{ fontWeight: 600, marginTop: 6 }}>{publicOrg.company_name || publicOrg.name}</div>
          </div>
        )}

        {error && <div className="error-msg">{error}</div>}

        <form onSubmit={handleSubmit}>
          {!mfaToken ? (
            <>
              <div className="form-group"><label htmlFor="orgslug">{t('login.org_slug', 'Organisation (identifiant) — optionnel')}</label>
                <input id="orgslug" value={orgSlug} onChange={e => { setOrgSlug(e.target.value); lookupOrg(e.target.value) }}
                  placeholder={t('login.org_slug_ph', 'ex. demo')} autoComplete="organization" />
              </div>
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

          <button type="submit" className="btn btn-primary" disabled={loading || !captchaAnswer}>
            {loading ? <div className="spinner" /> : mfaToken ? t('login.mfa_verify', 'Vérifier') : t('login.submit', 'Se connecter')}
          </button>
          {!captchaAnswer && !mfaToken && !loading && (
            <p className="text-center" style={{ color: 'var(--gray-600)', fontSize: '0.85rem', marginTop: 8 }}>{t('login.captcha', 'Veuillez résoudre le CAPTCHA')}</p>
          )}
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
    </>
  )
}
