import { useEffect, useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import { useAuth } from '../hooks/useAuth'
import { useVault } from '../hooks/useVault'
import { useT } from '../i18n/I18nContext'
import { exportDirectionPDF, type DirectionPreview } from '../lib/pdfExport'
import { encryptSection, sectionDigest, getSessionDEK } from '../lib/vault'
import {
  decryptSectionsForDisplay,
  prepareSectionsForSave,
  preparePreviewForPdf,
  needsUnlock,
  previewNeedsDecryption,
  VaultLockedError,
  type ApiSection,
  type ResolvedSection,
} from '../lib/minuteCrypto'

interface PublicationEntry {
  id: number
  published_by_name: string | null
  published_at: string
  pdf_sha256: string
  sections_count: number
}

interface MinuteData {
  id: number
  meeting_id: number
  status: string
  is_encrypted: boolean
  created_by_id: number
  created_by_name: string | null
  validated_by_id: number | null
  validated_by_name: string | null
  validated_at: string | null
  sections: ApiSection[]
  publications: PublicationEntry[]
}

interface MeetingInfo {
  id: number
  title: string
  date: string
}

async function sha256Hex(data: Uint8Array): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

function bytesToB64(bytes: Uint8Array): string {
  let binary = ''
  bytes.forEach(b => binary += String.fromCharCode(b))
  return btoa(binary)
}

const BUREAU_ROLES = ['president', 'vice_president', 'secretaire']

export default function MinutesPage() {
  const { meetingId } = useParams<{ meetingId: string }>()
  const navigate = useNavigate()
  const { token, user } = useAuth()
  const { t } = useT()
  const vault = useVault()
  const h = { Authorization: `Bearer ${token}` }

  const [meeting, setMeeting] = useState<MeetingInfo | null>(null)
  const [minute, setMinute] = useState<MinuteData | null>(null)
  const [sections, setSections] = useState<ResolvedSection[]>([])
  const [showPreview, setShowPreview] = useState(false)
  const [previewSections, setPreviewSections] = useState<ResolvedSection[]>([])
  const [previewMeta, setPreviewMeta] = useState<DirectionPreview | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [validating, setValidating] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  // Track whether we already prompted for vault unlock
  const [vaultPrompted, setVaultPrompted] = useState(false)

  useEffect(() => { loadData() }, [meetingId])

  async function loadData() {
    if (!meetingId) return
    try {
      const mr = await fetch(`/api/meetings/${meetingId}`, { headers: h })
      if (!mr.ok) throw new Error('Réunion non trouvée')
      const meetingData = await mr.json()
      setMeeting(meetingData)

      const mint = await fetch(`/api/meetings/${meetingId}/minute`, { headers: h })
      if (mint.ok) {
        const data: MinuteData = await mint.json()
        setMinute(data)

        const resolved = await decryptSectionsForDisplay(data.sections)
        setSections(resolved)

        if (needsUnlock(data.sections) && !vaultPrompted) {
          setErr(t('vault.minutes_locked'))
          setVaultPrompted(true)
        }
      }
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function createMinute() {
    if (!meetingId) return
    setCreating(true)
    setErr(null)
    try {
      const encoder = new TextEncoder()
      let sectionsPayload: any[]

      const dek = getSessionDEK()
      if (dek) {
        // Vault active — encrypt the initial empty section
        const pt = encoder.encode('')
        const encrypted = await encryptSection(dek, pt)
        const digest = await sectionDigest(pt, dek)
        sectionsPayload = [{
          position: 0,
          title: 'Introduction',
          content: bytesToB64(encrypted.ciphertext),
          nonce: bytesToB64(encrypted.nonce),
          content_digest: bytesToB64(digest),
          visibility: 'interne',
        }]
      } else {
        // Plaintext
        const toB64 = (str: string) => {
          const bytes = encoder.encode(str)
          let binary = ''
          bytes.forEach(b => binary += String.fromCharCode(b))
          return btoa(binary)
        }
        sectionsPayload = [{
          position: 0, title: 'Introduction', content: toB64(''), visibility: 'interne',
        }]
      }

      const r = await fetch(`/api/meetings/${meetingId}/minutes`, {
        method: 'POST',
        headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: sectionsPayload }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }
      const data: MinuteData = await r.json()
      setMinute(data)
      const resolved = await decryptSectionsForDisplay(data.sections)
      setSections(resolved)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setCreating(false)
    }
  }

  function addSection() {
    setSections(prev => [...prev, {
      id: null, position: prev.length, title: '', content: '',
      visibility: 'interne', _encrypted: null, _originalPlaintext: '',
    }])
  }

  function removeSection(idx: number) {
    setSections(prev => prev.filter((_, i) => i !== idx).map((s, i) => ({
      ...s, position: i,
      _encrypted: null,
      _originalPlaintext: s.content,
    })))
  }

  function moveSection(idx: number, dir: -1 | 1) {
    setSections(prev => {
      const next = [...prev]
      const target = idx + dir
      if (target < 0 || target >= next.length) return prev
      ;[next[idx], next[target]] = [next[target], next[idx]]
      return next.map((s, i) => ({ ...s, position: i }))
    })
  }

  async function saveSections(e: FormEvent) {
    e.preventDefault()
    if (!minute) return
    setSaving(true)
    setErr(null)
    try {
      const forSave = await prepareSectionsForSave(sections)

      const r = await fetch(`/api/minutes/${minute.id}/sections`, {
        method: 'PUT',
        headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: forSave }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }
      const updated: MinuteData = await r.json()
      setMinute(updated)
      const resolved = await decryptSectionsForDisplay(updated.sections)
      setSections(resolved)
      setMsg(t('minutes.saved'))
      setTimeout(() => setMsg(null), 3000)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleValidate() {
    if (!minute) return
    setValidating(true)
    setErr(null)
    try {
      const r = await fetch(`/api/minutes/${minute.id}/validate`, { method: 'POST', headers: h })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }
      setMsg(t('minutes.validated'))
      setTimeout(() => setMsg(null), 3000)
      const mr = await fetch(`/api/minutes/${minute.id}`, { headers: h })
      if (mr.ok) setMinute(await mr.json())
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setValidating(false)
    }
  }

  async function loadPreview() {
    if (!minute) return
    try {
      const r = await fetch(`/api/minutes/${minute.id}/direction-preview`, { headers: h })
      if (!r.ok) throw new Error('Erreur')
      const data: DirectionPreview = await r.json()

      // If the preview has encrypted sections, decrypt them for PDF generation
      let processedPreview = data
      if (previewNeedsDecryption(data)) {
        try {
          processedPreview = await preparePreviewForPdf(data)
        } catch (e) {
          if (e instanceof VaultLockedError) {
            setErr(t('vault.minutes_locked_preview'))
            return
          }
          throw e
        }
      }

      setPreviewMeta(processedPreview)
      // Decode sections for display
      const decoder = new TextDecoder()
      const displaySections: ResolvedSection[] = processedPreview.sections.map(s => {
        let plaintext = ''
        if (s.content) {
          const binary = atob(s.content)
          const bytes = new Uint8Array(binary.length)
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
          plaintext = decoder.decode(bytes)
        }
        return {
          id: null as number | null,
          position: s.position,
          title: s.title,
          visibility: s.visibility || 'partage',
          content: plaintext,
          _encrypted: null,
          _originalPlaintext: plaintext,
        }
      })
      setPreviewSections(displaySections)
      setShowPreview(true)
    } catch (e: any) {
      setErr(e.message)
    }
  }

  async function handleExportAndPublish() {
    if (!minute || !previewMeta) return
    setExporting(true)
    setErr(null)
    try {
      // If preview has encrypted sections, decrypt first
      let pdfPreview = previewMeta
      if (previewNeedsDecryption(pdfPreview)) {
        try {
          pdfPreview = await preparePreviewForPdf(pdfPreview)
        } catch (e) {
          if (e instanceof VaultLockedError) {
            setErr(t('vault.minutes_locked_preview'))
            setExporting(false)
            return
          }
          throw e
        }
      }

      // 1. Generate PDF client-side
      const pdfBytes = await exportDirectionPDF(pdfPreview)

      // 2. Compute SHA-256 via WebCrypto
      const sha256 = await sha256Hex(pdfBytes)

      // 3. Call /publish
      const r = await fetch(`/api/minutes/${minute.id}/publish`, {
        method: 'POST',
        headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ pdf_sha256: sha256 }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }

      // 4. Download the file
      const blob = new Blob([pdfBytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `PV-direction-${minute.id}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      // 5. Refresh to get updated status + publication history
      const mr = await fetch(`/api/minutes/${minute.id}`, { headers: h })
      if (mr.ok) setMinute(await mr.json())

      setMsg(t('minutes.published'))
      setTimeout(() => setMsg(null), 3000)
      setShowPreview(false)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setExporting(false)
    }
  }

  const isCreator = minute && user?.id === minute.created_by_id
  const isBureau = minute && user?.delegue_role && BUREAU_ROLES.includes(user.delegue_role)

  const statusLabel = (s: string) => {
    if (s === 'brouillon') return t('minutes.status_brouillon')
    if (s === 'valide') return t('minutes.status_valide')
    if (s === 'diffuse') return t('minutes.status_diffuse')
    return s
  }

  // Has the PV been modified since last publication? Published + not valide => obsolete
  const isPublishedObsolete = minute?.status === 'brouillon' && minute?.publications?.length > 0

  // Is the vault locked while there are encrypted sections?
  const vaultNeedsUnlock = minute && needsUnlock(minute.sections)

  // Is the export button disabled due to vault lock?
  const exportDisabledVault = vault.status === 'locked' && previewMeta && previewNeedsDecryption(previewMeta)

  if (loading) return <><NavBar /><div className="dashboard"><p>{t('common.loading')}</p></div></>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        {/* Vault locked banner */}
        {vaultNeedsUnlock && (
          <div style={{
            background: '#fff5f5', border: '1px solid #fed7d7',
            padding: '12px 16px', borderRadius: '8px', marginBottom: '16px',
            color: '#c53030', fontSize: '.9rem',
          }}>
            🔒 {t('vault.minutes_locked')}
          </div>
        )}

        {/* Obsolescence banner */}
        {isPublishedObsolete && (
          <div style={{
            background: '#fff3cd', border: '1px solid #ffc107',
            padding: '12px 16px', borderRadius: '8px', marginBottom: '16px',
            color: '#856404', fontSize: '.9rem', fontWeight: 600,
          }}>
            ⚠️ {t('minutes.obsolete_warning')}
          </div>
        )}

        {/* Preview Modal */}
        {showPreview && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.7)', zIndex: 2000,
            display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
            paddingTop: '5vh', overflow: 'auto',
          }} onClick={() => setShowPreview(false)}>
            <div style={{
              background: '#fff', borderRadius: '12px', maxWidth: '800px', width: '90%',
              maxHeight: '85vh', overflow: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
            }} onClick={e => e.stopPropagation()}>
              <div style={{
                background: '#c53030', color: '#fff', padding: '16px 24px',
                textAlign: 'center', fontWeight: 700, fontSize: '1.1rem',
                borderRadius: '12px 12px 0 0', letterSpacing: '0.5px',
              }}>
                {t('minutes.preview_banner')}
              </div>
              <div style={{ padding: '24px' }}>
                <p style={{
                  background: '#fff5f5', border: '1px solid #fed7d7',
                  padding: '12px 16px', borderRadius: '8px', color: '#c53030',
                  fontSize: '.85rem', marginBottom: '20px',
                }}>
                  {t('minutes.preview_warning')}
                </p>
                {previewSections.length === 0 ? (
                  <p style={{ color: 'var(--gray-600)', textAlign: 'center', padding: 40 }}>
                    Aucune section à afficher pour la direction.
                  </p>
                ) : (
                  previewSections.map((s, i) => (
                    <div key={i} style={{
                      marginBottom: '24px', padding: '16px',
                      border: '1px solid var(--gray-300)', borderRadius: '8px', background: '#f7fafc',
                    }}>
                      <h3 style={{ marginBottom: '8px', fontSize: '1rem' }}>{i + 1}. {s.title}</h3>
                      <div style={{ whiteSpace: 'pre-wrap', fontSize: '.9rem', color: '#2d3748', lineHeight: 1.6 }}>
                        {s.content}
                      </div>
                    </div>
                  ))
                )}
                <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                  <button onClick={() => setShowPreview(false)} className="btn"
                    style={{ flex: 1 }}>
                    {t('minutes.close_preview')}
                  </button>
                  {previewSections.length > 0 && minute?.status === 'valide' && isBureau && (
                    <button onClick={handleExportAndPublish} className="btn btn-primary"
                      disabled={exporting || !!exportDisabledVault}
                      title={exportDisabledVault ? t('vault.minutes_locked_preview') : undefined}
                      style={{ flex: 1, background: '#2b6cb0', color: '#fff', border: 'none' }}>
                      {exporting ? <div className="spinner" /> : t('minutes.export_and_publish')}
                    </button>
                  )}
                </div>
                {exportDisabledVault && previewSections.length > 0 && (
                  <p style={{ color: '#c53030', fontSize: '.8rem', marginTop: '8px', textAlign: 'center' }}>
                    {t('vault.minutes_locked_preview')}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="card mb-24">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: minute ? '16px' : '0' }}>
            <div>
              <h2>{t('minutes.title')}</h2>
              <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
                {meeting?.title || `Réunion #${meetingId}`}
                {minute && (
                  <span style={{
                    marginLeft: '10px', padding: '2px 8px', borderRadius: '4px', fontSize: '.75rem', fontWeight: 600,
                    background: minute.status === 'valide' ? '#c6f6d5' : minute.status === 'diffuse' ? '#bee3f8' : '#fefcbf',
                    color: minute.status === 'valide' ? '#276749' : minute.status === 'diffuse' ? '#2a4365' : '#975a16',
                  }}>
                    {statusLabel(minute.status)}
                  </span>
                )}
              </p>
              {minute?.validated_by_name && (
                <p style={{ color: 'var(--gray-600)', fontSize: '.8rem', marginTop: 4 }}>
                  {t('minutes.validated_by')} {minute.validated_by_name} {t('minutes.validated_at')} {minute.validated_at ? new Date(minute.validated_at).toLocaleString() : ''}
                </p>
              )}
              {/* Vault status in header */}
              {vault.status !== 'disabled' && (
                <p style={{
                  marginTop: '8px', fontSize: '.8rem',
                  color: vault.status === 'unlocked' ? '#276749' : '#975a16',
                  fontWeight: 600,
                }}>
                  {vault.status === 'unlocked' ? t('vault.status_unlocked') : t('vault.status_locked')}
                </p>
              )}
            </div>
            <button onClick={() => navigate('/meetings')} className="link" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '.85rem' }}>
              {t('minutes.back_to_meeting')}
            </button>
          </div>
        </div>

        {/* Publication history */}
        {minute && minute.publications && minute.publications.length > 0 && (
          <div className="card mb-24" style={{ background: '#f7fafc' }}>
            <h3 style={{ marginBottom: '12px', fontSize: '.95rem' }}>{t('minutes.publication_history')}</h3>
            <table style={{ width: '100%', fontSize: '.85rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--gray-300)', textAlign: 'left' }}>
                  <th style={{ padding: '4px 8px' }}>{t('minutes.pub_date')}</th>
                  <th style={{ padding: '4px 8px' }}>{t('minutes.pub_by')}</th>
                  <th style={{ padding: '4px 8px' }}>{t('minutes.pub_sections')}</th>
                  <th style={{ padding: '4px 8px' }}>{t('minutes.pub_hash')}</th>
                </tr>
              </thead>
              <tbody>
                {minute.publications.map((pub) => (
                  <tr key={pub.id} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                    <td style={{ padding: '6px 8px' }}>{new Date(pub.published_at).toLocaleString()}</td>
                    <td style={{ padding: '6px 8px' }}>{pub.published_by_name || '—'}</td>
                    <td style={{ padding: '6px 8px' }}>{pub.sections_count}</td>
                    <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: '.75rem' }}>
                      {pub.pdf_sha256.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* No minute yet */}
        {!minute && (
          <div className="card mb-24" style={{ textAlign: 'center', padding: '40px' }}>
            <p style={{ color: 'var(--gray-600)', marginBottom: '20px' }}>{t('minutes.no_minute')}</p>
            <button onClick={createMinute} className="btn btn-primary" disabled={creating}>
              {creating ? <div className="spinner" /> : t('minutes.create')}
            </button>
          </div>
        )}

        {/* Section Editor */}
        {minute && (
          <form onSubmit={saveSections}>
            {/* Title hint for vault-enabled orgs */}
            {vault.status !== 'disabled' && (
              <div style={{
                background: '#fffff0', border: '1px solid #e2e8f0',
                padding: '8px 14px', borderRadius: '6px', marginBottom: '12px',
                color: '#744210', fontSize: '.8rem', fontStyle: 'italic',
              }}>
                💡 {t('vault.title_hint')}
              </div>
            )}
            {sections.map((s, idx) => (
              <div key={idx} className="card mb-16" style={{
                borderLeft: `4px solid ${s.visibility === 'interne' ? '#e53e3e' : '#38a169'}`,
              }}>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ fontWeight: 700, color: 'var(--gray-600)', fontSize: '.8rem', minWidth: '24px' }}>
                    {idx + 1}.
                  </span>
                  <input
                    value={s.title}
                    onChange={e => setSections(prev => prev.map((ss, i) => i === idx ? { ...ss, title: e.target.value } : ss))}
                    placeholder={t('minutes.section_title')}
                    style={{
                      flex: 1, minWidth: '200px', padding: '8px 12px',
                      border: '1.5px solid var(--gray-300)', borderRadius: 'var(--radius)',
                    }}
                  />
                  <select
                    value={s.visibility}
                    onChange={e => setSections(prev => prev.map((ss, i) => i === idx ? {
                      ...ss,
                      visibility: e.target.value,
                      _encrypted: null,
                      _originalPlaintext: ss.content,
                    } : ss))}
                    style={{
                      padding: '8px 12px', border: '1.5px solid var(--gray-300)',
                      borderRadius: 'var(--radius)', fontSize: '.85rem',
                      background: s.visibility === 'interne' ? '#fff5f5' : '#f0fff4',
                      color: s.visibility === 'interne' ? '#c53030' : '#276749',
                      fontWeight: 600, cursor: 'pointer',
                    }}
                  >
                    <option value="interne">{t('minutes.visibility_interne')}</option>
                    <option value="partage">{t('minutes.visibility_partage')}</option>
                  </select>
                  {/* Encryption indicator */}
                  {vault.status !== 'disabled' && (
                    <span title={s._encrypted ? t('vault.section_encrypted') : t('vault.section_plaintext')}
                      style={{ fontSize: '.8rem' }}>
                      {s._encrypted ? '🔒' : '📝'}
                    </span>
                  )}
                  <button type="button" onClick={() => moveSection(idx, -1)} disabled={idx === 0}
                    style={{ background: 'none', border: 'none', cursor: idx === 0 ? 'default' : 'pointer', fontSize: '1.2rem', opacity: idx === 0 ? 0.3 : 1 }}>
                    ↑
                  </button>
                  <button type="button" onClick={() => moveSection(idx, 1)} disabled={idx === sections.length - 1}
                    style={{ background: 'none', border: 'none', cursor: idx === sections.length - 1 ? 'default' : 'pointer', fontSize: '1.2rem', opacity: idx === sections.length - 1 ? 0.3 : 1 }}>
                    ↓
                  </button>
                  <button type="button" onClick={() => removeSection(idx)}
                    style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: '1.2rem', fontWeight: 700 }}>
                    ×
                  </button>
                </div>
                <textarea
                  value={s.content}
                  onChange={e => setSections(prev => prev.map((ss, i) => i === idx ? { ...ss, content: e.target.value } : ss))}
                  placeholder={t('minutes.section_content')}
                  rows={4}
                  style={{
                    width: '100%', padding: '10px 12px', border: '1.5px solid var(--gray-300)',
                    borderRadius: 'var(--radius)', resize: 'vertical', fontFamily: 'inherit', fontSize: '.9rem',
                  }}
                />
              </div>
            ))}

            <button type="button" onClick={addSection}
              style={{
                background: 'none', border: '1.5px dashed var(--gray-400)', cursor: 'pointer',
                fontSize: '.85rem', padding: '10px 16px', borderRadius: 'var(--radius)',
                width: '100%', textAlign: 'center', marginBottom: '16px', color: 'var(--gray-700)',
              }}>
              {t('minutes.add_section')}
            </button>

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? <div className="spinner" /> : t('minutes.save_sections')}
              </button>
              <button type="button" onClick={loadPreview} className="btn"
                style={{ background: '#edf2f7', color: '#2d3748', border: '1.5px solid var(--gray-400)' }}>
                {t('minutes.preview_direction')}
              </button>
              <div style={{ flex: 1 }} />
              <div style={{ textAlign: 'right' }}>
                <button
                  type="button" onClick={handleValidate}
                  disabled={!!isCreator || validating || minute.status === 'valide' || minute.status === 'diffuse'}
                  className="btn"
                  style={{
                    background: (isCreator || minute.status === 'valide' || minute.status === 'diffuse') ? '#e2e8f0' : '#c6f6d5',
                    color: (isCreator || minute.status === 'valide' || minute.status === 'diffuse') ? '#a0aec0' : '#276749',
                    border: 'none', cursor: (isCreator || minute.status === 'valide' || minute.status === 'diffuse') ? 'not-allowed' : 'pointer',
                    fontWeight: 700,
                  }}
                  title={isCreator ? t('minutes.validate_disabled') : ''}
                >
                  {validating ? <div className="spinner" /> : t('minutes.validate')}
                </button>
                {isCreator && (
                  <small style={{ display: 'block', color: '#e53e3e', fontSize: '.75rem', marginTop: '4px', maxWidth: '280px' }}>
                    {t('minutes.validate_disabled')}
                  </small>
                )}
              </div>
            </div>
          </form>
        )}
      </div>
    </>
  )
}
