import { useEffect, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { useT } from '../i18n/I18nContext'
import { WrongPasswordError } from '../lib/vault'
import { b64encode, decryptSharedSections, unwrapSharedDEK, type SharedSection } from '../lib/shareLink'
import { exportDirectionPDF, type DirectionPreview } from '../lib/pdfExport'

interface ShareInfo {
  token: string
  org_name: string
  minute_title: string
  meeting_title: string
  meeting_date: string | null
  expires_at: string | null
  revoked: boolean
  valid: boolean
}

interface SharedContent {
  token: string
  minute_title: string
  meeting_title: string
  meeting_date: string | null
  org_name: string
  envelope: string
  sections: SharedSection[]
}

/**
 * Page publique de lecture d'un PV partagé avec la direction.
 * Pas de compte requis : lien + code de lecture transmis séparément.
 * Tout le déchiffrement se fait dans le navigateur — le serveur ne voit
 * jamais le clair.
 */
export default function ShareView() {
  const { token } = useParams<{ token: string }>()
  const { t } = useT()

  const [info, setInfo] = useState<ShareInfo | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error' | 'gone'>('loading')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const [code, setCode] = useState('')
  const [unlocking, setUnlocking] = useState(false)
  const [wrongCode, setWrongCode] = useState(false)
  const [sections, setSections] = useState<{ position: number; title: string; text: string }[] | null>(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    if (!token) return
    fetch(`/api/share-links/${token}`)
      .then(r => {
        if (r.status === 410) { setStatus('gone'); return null }
        if (!r.ok) { setStatus('error'); return null }
        return r.json()
      })
      .then(data => {
        if (data) { setInfo(data); setStatus('ready') }
      })
      .catch(() => setStatus('error'))
  }, [token])

  async function openShare(e: FormEvent) {
    e.preventDefault()
    if (!token || !code.trim()) return
    setUnlocking(true); setWrongCode(false); setErrorMsg(null)
    try {
      const r = await fetch(`/api/share-links/${token}/content`)
      if (r.status === 410) { setStatus('gone'); return }
      if (!r.ok) throw new Error('Impossible de charger le PV')
      const content: SharedContent = await r.json()

      // Déchiffrement local : DEK ← enveloppe + code → sections en clair
      const dek = await unwrapSharedDEK(content.envelope, code.trim().toUpperCase())
      const plain = await decryptSharedSections(dek, content.sections)
      setSections(plain)
      // Zéro le DEK après usage
      dek.fill(0)
    } catch (e: unknown) {
      if (e instanceof WrongPasswordError) {
        setWrongCode(true)
      } else {
        setErrorMsg((e as Error).message || 'Erreur de déchiffrement')
      }
    } finally {
      setUnlocking(false)
    }
  }

  async function exportPdf() {
    if (!sections || !info) return
    setExporting(true)
    try {
      const preview: DirectionPreview = {
        minute_id: 0,
        meeting_title: info.meeting_title || null,
        validated_by_name: null,
        validated_at: null,
        sections: sections.map(s => ({
          position: s.position,
          title: s.title,
          content: b64encode(new TextEncoder().encode(s.text)),
          visibility: 'partage',
        })),
        generated_at: new Date().toISOString(),
      }
      const pdfBytes = await exportDirectionPDF(preview)
      const blob = new Blob([pdfBytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `PV-direction-${info.meeting_title.replace(/\s+/g, '-').slice(0, 40) || 'reunion'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e: any) {
      setErrorMsg(e.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--gray-100)', padding: '40px 16px' }}>
      <div className="card" style={{ maxWidth: 720, margin: '0 auto', background: '#fff' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: '2.2rem' }}>🔐</div>
          <h1 style={{ fontSize: '1.3rem', marginTop: 8 }}>{info?.org_name || 'Délégation du personnel'}</h1>
        </div>

        {status === 'loading' && <div style={{ textAlign: 'center', padding: 40 }}><div className="spinner" /></div>}

        {status === 'error' && (
          <div className="error-msg">Ce lien de lecture est introuvable.</div>
        )}

        {status === 'gone' && (
          <div className="error-msg" style={{ textAlign: 'center', padding: 24 }}>
            ⛔ Ce lien a expiré ou a été révoqué.<br />
            <small>Contactez le bureau de la délégation pour un nouveau lien.</small>
          </div>
        )}

        {status === 'ready' && !sections && (
          <>
            <p style={{ textAlign: 'center', color: 'var(--gray-600)', marginBottom: 20 }}>
              {info?.meeting_title ? (
                <>Procès-verbal de la réunion <strong>{info.meeting_title}</strong>
                  {info.meeting_date ? <> du <strong>{new Date(info.meeting_date).toLocaleDateString('fr-LU')}</strong></> : null}</>
              ) : 'Procès-verbal de réunion'}
              <br />
              <small>Saisissez le code de lecture communiqué par le bureau pour consulter le PV.</small>
            </p>

            <form onSubmit={openShare} style={{ maxWidth: 360, margin: '0 auto' }}>
              <div className="form-group">
                <label>Code de lecture</label>
                <input
                  value={code}
                  onChange={e => { setCode(e.target.value.toUpperCase()); setWrongCode(false) }}
                  placeholder="EX : 4K7M2P9X"
                  style={{ textAlign: 'center', letterSpacing: 4, textTransform: 'uppercase', fontWeight: 700 }}
                  maxLength={8}
                  autoFocus
                />
              </div>
              {wrongCode && <div className="error-msg">Code incorrect — vérifiez auprès du bureau de la délégation.</div>}
              {errorMsg && <div className="error-msg">{errorMsg}</div>}
              <button type="submit" className="btn btn-primary" disabled={unlocking || code.length < 4} style={{ width: '100%' }}>
                {unlocking ? <div className="spinner" /> : '🔓 Consulter le PV'}
              </button>
              {info?.expires_at && (
                <p style={{ textAlign: 'center', color: 'var(--gray-500)', fontSize: '.75rem', marginTop: 12 }}>
                  Lien valable jusqu'au {new Date(info.expires_at).toLocaleDateString('fr-LU')}
                </p>
              )}
            </form>
          </>
        )}

        {status === 'ready' && sections && (
          <>
            <div className="success-msg" style={{ textAlign: 'center' }}>
              ✅ PV déchiffré dans votre navigateur — rien n'a transité en clair par le serveur.
            </div>
            <h2 style={{ fontSize: '1.05rem', margin: '20px 0 4px' }}>{info?.meeting_title}</h2>
            <p style={{ color: 'var(--gray-500)', fontSize: '.8rem', marginBottom: 16 }}>
              {info?.org_name} — document de lecture, ne pas diffuser
            </p>
            {sections.map((s, i) => (
              <div key={i} style={{ marginBottom: 20, padding: 16, border: '1px solid var(--gray-300)', borderRadius: 8, background: '#f7fafc' }}>
                <h3 style={{ marginBottom: 8, fontSize: '.95rem' }}>{i + 1}. {s.title}</h3>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: '.88rem', color: '#2d3748', lineHeight: 1.6 }}>{s.text}</div>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn" onClick={() => { setSections(null); setCode('') }} style={{ flex: 1 }}>
                ← Saisir un autre code
              </button>
              <button className="btn btn-primary" onClick={exportPdf} disabled={exporting} style={{ flex: 1 }}>
                {exporting ? <div className="spinner" /> : '⬇️ Exporter en PDF'}
              </button>
            </div>
          </>
        )}
      </div>
      <p style={{ textAlign: 'center', color: 'var(--gray-500)', fontSize: '.75rem', marginTop: 20 }}>
        {t('app.title')} — lecture sécurisée
      </p>
    </div>
  )
}
