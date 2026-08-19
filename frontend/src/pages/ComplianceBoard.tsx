import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import * as api from '../api/client'

const STATUS_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  ok:   { bg: '#e6f4ea', color: '#137333', label: '✅' },
  warn: { bg: '#fef7e0', color: '#b06000', label: '⚠️' },
  due:  { bg: '#fce8e6', color: '#c5221f', label: '🔴' },
  na:   { bg: '#f1f3f4', color: '#5f6368', label: '—' },
  info: { bg: '#e8f0fe', color: '#1a73e8', label: 'ℹ️' },
}

const EVENT_TYPE_META: Record<string, { titleKey: string; icon: string }> = {
  plenary_assembly:     { titleKey: 'compliance.plenary_label', icon: '🗣️' },
  eco_financial_report: { titleKey: 'compliance.eco_label', icon: '📊' },
  names_communication:  { titleKey: 'compliance.names_label', icon: '📝' },
}

export default function ComplianceBoard() {
  const { user } = useAuth()
  const { t } = useT()
  const [data, setData] = useState<api.ComplianceOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [showEvent, setShowEvent] = useState<string | null>(null)
  const [evDate, setEvDate] = useState('')
  const [evNotes, setEvNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const isBureau = !!user && (user.role === 'admin' || user.delegue_role === 'president' || user.delegue_role === 'vice_president' || user.delegue_role === 'secretaire')

  useEffect(() => { load() }, [])

  async function load() {
    try {
      setData(await api.getComplianceOverview())
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  async function addEvent(type: string) {
    setSaving(true); setErr(null)
    try {
      await api.createComplianceEvent({ event_type: type, event_date: evDate || undefined, notes: evNotes || undefined })
      setShowEvent(null); setEvDate(''); setEvNotes('')
      await load()
    } catch (e: any) { setErr(e.message) } finally { setSaving(false) }
  }

  async function removeEvent(id: number) {
    if (!confirm(t('compliance.event_delete_confirm'))) return
    try {
      await api.deleteComplianceEvent(id)
      await load()
    } catch (e: any) { setErr(e.message) }
  }

  function fmt(iso: string | null) {
    if (!iso) return ''
    return new Date(iso).toLocaleDateString()
  }

  if (!user) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>⚖️ {t('compliance.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('compliance.subtitle')}
        </p>

        {err && <div className="error-msg">{err}</div>}
        {loading && <div className="spinner" />}

        {data && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 12 }}>
              {data.items.map(it => {
                const st = STATUS_STYLE[it.status]
                return (
                  <div key={it.key} className="card" style={{ padding: '14px 16px', borderLeft: `4px solid ${st.color}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div>
                        <h3 style={{ margin: 0, fontSize: '.95rem' }}>{it.title}</h3>
                        <p style={{ margin: '2px 0 6px', fontSize: '.72rem', color: 'var(--gray-600)' }}>
                          {t('compliance.legal_ref')}: <strong>{it.legal_ref}</strong>
                        </p>
                      </div>
                      <span style={{ fontSize: '1rem' }}>{st.label}</span>
                    </div>
                    <p style={{ margin: 0, fontSize: '.82rem', color: st.color }}>{it.detail}</p>
                    {isBureau && ['plenary', 'eco', 'names'].includes(it.key) && (
                      <div style={{ marginTop: 8 }}>
                        {showEvent === it.key ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                            <input type="date" value={evDate} onChange={e => setEvDate(e.target.value)} />
                            <input type="text" placeholder={t('compliance.notes_placeholder')} value={evNotes} onChange={e => setEvNotes(e.target.value)} maxLength={1000} />
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button className="btn btn-primary" style={{ fontSize: '.75rem', padding: '4px 10px' }} onClick={() => addEvent(it.key === 'plenary' ? 'plenary_assembly' : it.key === 'eco' ? 'eco_financial_report' : 'names_communication')} disabled={saving}>
                                {saving ? '…' : t('compliance.save')}
                              </button>
                              <button className="btn" style={{ fontSize: '.75rem', padding: '4px 10px', background: 'var(--gray-300)' }} onClick={() => setShowEvent(null)}>
                                {t('organigramme.cancel')}
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button className="btn" style={{ fontSize: '.75rem', padding: '4px 10px', background: 'var(--blue)', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }} onClick={() => { setShowEvent(it.key); setEvDate(''); setEvNotes('') }}>
                            {it.key === 'plenary' ? '🗣️ ' : it.key === 'eco' ? '📊 ' : '📝 '}{t('compliance.log_event')}
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <h2 style={{ fontSize: '1.1rem', marginTop: 28 }}>📜 {t('compliance.history')}</h2>
            {data.events.length === 0 ? (
              <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>{t('compliance.history_empty')}</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('compliance.event')}</th>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('compliance.event_date')}</th>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('notices.posted_by')}</th>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('compliance.notes')}</th>
                    {isBureau && <th style={{ padding: 6 }} />}
                  </tr>
                </thead>
                <tbody>
                  {data.events.map(ev => (
                    <tr key={ev.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                      <td style={{ padding: 6 }}>
                        {EVENT_TYPE_META[ev.event_type]?.icon} {t(EVENT_TYPE_META[ev.event_type]?.titleKey || 'compliance.event')}
                      </td>
                      <td style={{ padding: 6 }}>{fmt(ev.event_date)}</td>
                      <td style={{ padding: 6 }}>{ev.created_by_name || '—'}</td>
                      <td style={{ padding: 6 }}>{ev.notes || '—'}</td>
                      {isBureau && (
                        <td style={{ padding: 6, textAlign: 'right' }}>
                          <button className="btn" style={{ fontSize: '.72rem', padding: '2px 8px', background: 'var(--gray-300)', border: 'none', borderRadius: 4, cursor: 'pointer', color: 'var(--red)' }} onClick={() => removeEvent(ev.id)}>🗑️</button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </>
  )
}
