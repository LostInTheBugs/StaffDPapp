import { useEffect, useState, type FormEvent } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'

interface Section {
  id: number | null
  position: number
  title: string
  visibility: string
  content: string
}

interface MinuteData {
  id: number
  meeting_id: number
  status: string
  created_by_id: number
  created_by_name: string | null
  validated_by_id: number | null
  validated_by_name: string | null
  validated_at: string | null
  sections: Section[]
}

interface MeetingInfo {
  id: number
  title: string
  date: string
}

function b64Encode(str: string): string {
  const bytes = new TextEncoder().encode(str)
  let binary = ''
  bytes.forEach(b => binary += String.fromCharCode(b))
  return btoa(binary)
}

function b64Decode(str: string): string {
  const binary = atob(str)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new TextDecoder().decode(bytes)
}

export default function MinutesPage() {
  const { meetingId } = useParams<{ meetingId: string }>()
  const navigate = useNavigate()
  const { token, user } = useAuth()
  const { t } = useT()
  const h = { Authorization: `Bearer ${token}` }

  const [meeting, setMeeting] = useState<MeetingInfo | null>(null)
  const [minute, setMinute] = useState<MinuteData | null>(null)
  const [sections, setSections] = useState<Section[]>([])
  const [showPreview, setShowPreview] = useState(false)
  const [previewSections, setPreviewSections] = useState<Section[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [validating, setValidating] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => { loadData() }, [meetingId])

  function decodeSections(secs: Section[]): Section[] {
    return secs.map(s => ({ ...s, content: s.content ? b64Decode(s.content) : '' }))
  }

  async function loadData() {
    if (!meetingId) return
    try {
      const mr = await fetch(`/api/meetings/${meetingId}`, { headers: h })
      if (!mr.ok) throw new Error('Réunion non trouvée')
      const meetingData = await mr.json()
      setMeeting(meetingData)

      const mint = await fetch(`/api/meetings/${meetingId}/minute`, { headers: h })
      if (mint.ok) {
        const data = await mint.json()
        setMinute(data)
        setSections(decodeSections(data.sections))
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
      const r = await fetch(`/api/meetings/${meetingId}/minutes`, {
        method: 'POST',
        headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections: [{ position: 0, title: 'Introduction', content: b64Encode(''), visibility: 'interne' }]
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }
      const data = await r.json()
      setMinute(data)
      setSections(decodeSections(data.sections))
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setCreating(false)
    }
  }

  function addSection() {
    setSections(prev => [...prev, {
      id: null, position: prev.length, title: '', content: '', visibility: 'interne',
    }])
  }

  function removeSection(idx: number) {
    setSections(prev => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, position: i })))
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
      const r = await fetch(`/api/minutes/${minute.id}/sections`, {
        method: 'PUT',
        headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sections: sections.map((s, i) => ({
            position: i, title: s.title, content: b64Encode(s.content), visibility: s.visibility,
          })),
        }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'Erreur' }))
        throw new Error(body.detail || 'Erreur')
      }
      const updated = await r.json()
      setMinute(updated)
      setSections(decodeSections(updated.sections))
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
      const data = await r.json()
      setPreviewSections(decodeSections(data.sections))
      setShowPreview(true)
    } catch (e: any) {
      setErr(e.message)
    }
  }

  const isCreator = minute && user?.id === minute.created_by_id

  const statusLabel = (s: string) => {
    if (s === 'brouillon') return t('minutes.status_brouillon')
    if (s === 'valide') return t('minutes.status_valide')
    if (s === 'diffuse') return t('minutes.status_diffuse')
    return s
  }

  if (loading) return <><NavBar /><div className="dashboard"><p>{t('common.loading')}</p></div></>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

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
                <button onClick={() => setShowPreview(false)} className="btn" style={{ marginTop: '16px', width: '100%' }}>
                  {t('minutes.close_preview')}
                </button>
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
            </div>
            <button onClick={() => navigate('/meetings')} className="link" style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '.85rem' }}>
              {t('minutes.back_to_meeting')}
            </button>
          </div>
        </div>

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
                    onChange={e => setSections(prev => prev.map((ss, i) => i === idx ? { ...ss, visibility: e.target.value } : ss))}
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
                  disabled={!!isCreator || validating || minute.status === 'valide'}
                  className="btn"
                  style={{
                    background: (isCreator || minute.status === 'valide') ? '#e2e8f0' : '#c6f6d5',
                    color: (isCreator || minute.status === 'valide') ? '#a0aec0' : '#276749',
                    border: 'none', cursor: (isCreator || minute.status === 'valide') ? 'not-allowed' : 'pointer',
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
