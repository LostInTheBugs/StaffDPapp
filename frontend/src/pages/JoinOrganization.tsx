import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import CaptchaWidget from '../components/CaptchaWidget'
import * as api from '../api/client'
import type { VaultEnvelope } from '../api/client'
import {
  unwrapDEK,
  wrapDEK,
} from '../lib/vault'
import { normalizeCode } from '../lib/vaultSession'

export default function JoinOrganization() {
  const [form, setForm] = useState({ invitation_code: '', first_name: '', last_name: '', email: '', password: '' })
  const [captchaId, setCaptchaId] = useState('')
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [vaultStep, setVaultStep] = useState<string | null>(null) // null | 'deriving' | 'encrypting'
  const { setAuth } = useAuth()
  const { t } = useT()
  const navigate = useNavigate()

  function update(field: string, value: string) { setForm(prev => ({ ...prev, [field]: value })) }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault(); setError(null)
    if (form.password.length < 6) { setError(t('join.error_password')); return }
    if (!captchaAnswer) { setError(t('join.captcha')); return }

    setLoading(true)
    try {
      let vault_envelope: VaultEnvelope | null = null

      // Try vault envelope exchange: if the org has a vault, the invitation
      // will have an envelope we can unwrap with the code.
      try {
        setVaultStep('deriving')
        const keyResp = await api.getJoinVaultEnvelope(form.invitation_code, form.email)

        // Got an envelope — unwrap DEK with code, re-wrap with password
        const normalized = normalizeCode(form.invitation_code)
        const params = JSON.parse(keyResp.kdf_params)
        const wrapped = Uint8Array.from(atob(keyResp.wrapped_dek), c => c.charCodeAt(0))
        const nonce = Uint8Array.from(atob(keyResp.nonce), c => c.charCodeAt(0))
        const salt = Uint8Array.from(atob(keyResp.kdf_salt), c => c.charCodeAt(0))

        const dek = await unwrapDEK(wrapped, nonce, normalized, salt, params)

        setVaultStep('encrypting')
        const newEnvelope = await wrapDEK(dek, form.password)

        vault_envelope = {
          wrapped_dek: btoa(String.fromCharCode(...newEnvelope.wrapped)),
          nonce: btoa(String.fromCharCode(...newEnvelope.nonce)),
          kdf_salt: btoa(String.fromCharCode(...newEnvelope.kdfSalt)),
          kdf_params: JSON.stringify(newEnvelope.kdfParams),
        }
      } catch (_) {
        // No vault or envelope not found — proceed without vault_envelope
        // (org may not have vault enabled, or invitation has no envelope)
      }

      setVaultStep(null)

      const tokenResp = await api.joinOrganization({
        ...form,
        captcha_id: captchaId,
        captcha_answer: captchaAnswer,
        vault_envelope,
      })

      localStorage.setItem('token', tokenResp.access_token)
      const dash = await api.getDashboard()
      setAuth(tokenResp.access_token, dash.user, dash.organization)
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message || t('join.error_code_invalid'))
    }
    finally {
      setLoading(false)
      setVaultStep(null)
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h2>{t('join.title')}</h2>
        <p className="subtitle">{t('join.subtitle')}</p>
        {error && <div className="error-msg">{error}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group"><label>{t('join.code')}</label>
            <input value={form.invitation_code} onChange={e => update('invitation_code', e.target.value.toUpperCase())}
              style={{ fontFamily:'monospace', letterSpacing:'2px', textTransform:'uppercase' }} required autoFocus maxLength={31} />
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
            <div className="form-group"><label>{t('join.firstname')}</label><input value={form.first_name} onChange={e => update('first_name', e.target.value)} required /></div>
            <div className="form-group"><label>{t('join.lastname')}</label><input value={form.last_name} onChange={e => update('last_name', e.target.value)} required /></div>
          </div>
          <div className="form-group"><label>{t('join.email')}</label><input type="email" value={form.email} onChange={e => update('email', e.target.value)} required /></div>
          <div className="form-group"><label>{t('join.password')}</label><input type="password" value={form.password} onChange={e => update('password', e.target.value)} required minLength={6} /></div>

          {vaultStep && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, color: 'var(--gray-600)', fontSize: '0.85rem' }}>
              <div className="spinner" />
              <span>{vaultStep === 'deriving' ? t('join.vault_deriving') : t('join.vault_encrypting')}</span>
            </div>
          )}

          <CaptchaWidget onCaptcha={(id, ans) => { setCaptchaId(id); setCaptchaAnswer(ans) }} />

          <button type="submit" className="btn btn-primary" disabled={loading || !captchaAnswer}>
            {loading ? <div className="spinner" /> : t('join.submit', 'Créer mon compte')}
          </button>
          {!captchaAnswer && !loading && (
            <p className="text-center" style={{ color: 'var(--gray-600)', fontSize: '0.85rem', marginTop: 8 }}>{t('join.captcha', 'Veuillez résoudre le CAPTCHA')}</p>
          )}
        </form>
        <p className="text-center mt-16"><Link to="/" className="link">← Retour</Link></p>
      </div>
    </div>
  )
}
