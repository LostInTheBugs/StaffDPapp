import { useState } from 'react'

export default function MfaSection() {
  const [qrCode, setQrCode] = useState<string | null>(null)
  const [setupCode, setSetupCode] = useState('')
  const [disablePass, setDisablePass] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const token = localStorage.getItem('token') || ''
  const headers = { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }

  async function setupMfa() {
    setErr(null); setMsg(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/mfa/setup', { method: 'POST', headers })
      if (!res.ok) throw new Error((await res.json()).detail)
      const data = await res.json()
      setQrCode(data.qr_code_b64)
      setMsg("Scannez le QR code avec votre app d'authentification, puis entrez le code.")
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  async function verifyMfa() {
    setErr(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/mfa/verify', { method: 'POST', headers, body: JSON.stringify({ totp_code: setupCode }) })
      if (!res.ok) throw new Error((await res.json()).detail)
      setMsg('MFA activé avec succès ! ✅'); setQrCode(null); setSetupCode('')
      setTimeout(() => window.location.reload(), 1500)
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  async function disableMfa() {
    setErr(null); setLoading(true)
    try {
      const res = await fetch('/api/auth/mfa/disable', { method: 'POST', headers, body: JSON.stringify({ password: disablePass }) })
      if (!res.ok) throw new Error((await res.json()).detail)
      setMsg('MFA désactivé.'); setDisablePass('')
      setTimeout(() => window.location.reload(), 1000)
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div>
      {msg && <div className="success-msg">{msg}</div>}
      {err && <div className="error-msg">{err}</div>}

      {qrCode ? (
        <div style={{ textAlign: 'center' }}>
          <img src={`data:image/png;base64,${qrCode}`} alt="QR Code MFA" style={{ maxWidth: 200, marginBottom: 16 }} />
          <div className="form-group">
            <label>Code de vérification</label>
            <input type="text" inputMode="numeric" autoComplete="one-time-code"
              value={setupCode} onChange={e => setSetupCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              maxLength={6} style={{ fontFamily:'monospace', fontSize:'1.3rem', textAlign:'center', letterSpacing:'4px' }} />
          </div>
          <button onClick={verifyMfa} className="btn btn-primary" disabled={loading || setupCode.length < 6}>
            {loading ? <div className="spinner" /> : 'Activer MFA'}
          </button>
          <p className="text-center mt-16">
            <button onClick={() => { setQrCode(null); setSetupCode(''); setMsg(null); setErr(null) }}
              className="link" style={{ background:'none', border:'none', cursor:'pointer' }}>
              Annuler
            </button>
          </p>
        </div>
      ) : (
        <>
          <button onClick={setupMfa} className="btn btn-secondary mb-16" disabled={loading}>
            {loading ? <div className="spinner" /> : '🔐 Configurer MFA'}
          </button>
          <div style={{ borderTop: '1px solid var(--gray-300)', paddingTop: 16 }}>
            <label style={{ fontWeight: 600, fontSize: '.88rem', display:'block', marginBottom:4 }}>
              Désactiver MFA (mot de passe requis)
            </label>
            <div style={{ display:'flex', gap:8 }}>
              <input type="password" value={disablePass} onChange={e => setDisablePass(e.target.value)}
                placeholder="Mot de passe" style={{ flex:1, padding:'8px 12px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)' }} />
              <button onClick={disableMfa} className="btn" style={{ background:'var(--red)', color:'#fff', padding:'8px 16px', flex:'none' }}
                disabled={loading || !disablePass}>
                Désactiver
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
