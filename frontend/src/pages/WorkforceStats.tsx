import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import Footer from '../components/Footer'
import * as api from '../api/client'
import { semesterLabel } from '../lib/semester'
import { exportWorkforceStatsPDF } from '../lib/workforceStatsPdf'
import { exportAnnualReportPDF } from '../lib/annualReportPdf'

export default function WorkforceStats() {
  const { t } = useT()
  const { user, token, organization } = useAuth()
  const [rows, setRows] = useState<api.WorkforceStat[]>([])
  const [latest, setLatest] = useState<api.WorkforceStat | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [year, setYear] = useState(String(new Date().getFullYear()))
  const [half, setHalf] = useState('1')
  const [male, setMale] = useState('')
  const [female, setFemale] = useState('')
  const [editId, setEditId] = useState<number | null>(null)
  const [editMale, setEditMale] = useState('')
  const [editFemale, setEditFemale] = useState('')
  const [pdfBusy, setPdfBusy] = useState(false)

  const isBureau = user?.delegue_role === 'president' || user?.delegue_role === 'vice_president' || user?.delegue_role === 'secretaire' || user?.role === 'admin'

  async function load() {
    try {
      const [r, l] = await Promise.all([api.listWorkforceStats(), api.getLatestWorkforceStat()])
      setRows(r)
      setLatest(l)
      setErr(null)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [token])

  async function create(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setErr(null)
    try {
      await api.createWorkforceStat({
        semester: `${year}-${half}`,
        male_count: parseInt(male, 10) || 0,
        female_count: parseInt(female, 10) || 0,
      })
      setYear(String(new Date().getFullYear())); setHalf('1'); setMale(''); setFemale('')
      setShowForm(false)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function saveEdit(id: number) {
    setErr(null)
    try {
      await api.updateWorkforceStat(id, {
        male_count: parseInt(editMale, 10) || 0,
        female_count: parseInt(editFemale, 10) || 0,
      })
      setEditId(null)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  async function remove(id: number) {
    if (!window.confirm('Supprimer ce rapport semestriel ?')) return
    setErr(null)
    try {
      await api.deleteWorkforceStat(id)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  async function downloadPDF() {
    setErr(null)
    setPdfBusy(true)
    try {
      const bytes = await exportWorkforceStatsPDF(rows, organization?.name ?? 'Délégation du personnel')
      const blob = new Blob([bytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `statistiques_effectif_${rows[0]?.semester ?? 'historique'}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setPdfBusy(false)
    }
  }

  // ── Rapport d'activité annuel ────────────────────────────────────
  const [reportYear, setReportYear] = useState(String(new Date().getFullYear()))
  const [reportBusy, setReportBusy] = useState(false)

  async function downloadAnnualReport() {
    setErr(null)
    setReportBusy(true)
    try {
      const data = await api.getAnnualReport(parseInt(reportYear, 10))
      const bytes = await exportAnnualReportPDF(data)
      const blob = new Blob([bytes], { type: 'application/pdf' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `rapport_activite_${reportYear}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setReportBusy(false)
    }
  }

  const total = latest ? latest.total : 0
  const malePct = total > 0 ? Math.round((latest!.male_count / total) * 100) : 0
  const femalePct = total > 0 ? Math.round((latest!.female_count / total) * 100) : 0

  return (
    <>
      <NavBar />
      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <h2>📊 {t('stats.title')}</h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              value={reportYear}
              onChange={(e) => setReportYear(e.target.value)}
              style={{ padding: '6px 8px', fontSize: '.85rem', borderRadius: 6, border: '1px solid var(--gray-300)' }}
              aria-label="Année du rapport"
            >
              {Array.from({ length: 5 }, (_, i) => String(new Date().getFullYear() - i)).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <button
              className="btn"
              style={{ padding: '6px 12px', fontSize: '.85rem', background: 'var(--green)', color: '#fff', border: 'none' }}
              onClick={downloadAnnualReport}
              disabled={reportBusy}
            >
              {reportBusy ? '…' : '📄 Rapport d\'activité annuel'}
            </button>
            <button
              className="btn"
              style={{ padding: '6px 12px', fontSize: '.85rem', background: 'var(--blue)', color: '#fff', border: 'none' }}
              onClick={downloadPDF}
              disabled={pdfBusy || rows.length === 0}
              title={rows.length === 0 ? t('stats.empty') : undefined}
            >
              {pdfBusy ? '…' : '🖨️ Rapport PDF'}
            </button>
          </div>
        </div>
        <p style={{ color: 'var(--gray-600)', marginBottom: 16 }}>
          {t('stats.subtitle')}
        </p>

        {err && <div className="error-msg">{err}</div>}

        {loading ? (
          <p>Chargement…</p>
        ) : (
          <>
            {latest && (
              <div className="card mb-24" style={{ borderColor: 'var(--green)' }}>
                <h3>👥 {t('stats.latest_card')} — {semesterLabel(latest.semester)}</h3>
                <div style={{ display: 'flex', gap: 32, marginTop: 12, flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#2563eb' }}>{latest.male_count}</div>
                    <div style={{ color: 'var(--gray-600)' }}>👨 Hommes</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: '#db2777' }}>{latest.female_count}</div>
                    <div style={{ color: 'var(--gray-600)' }}>👩 Femmes</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '2rem', fontWeight: 700 }}>{total}</div>
                    <div style={{ color: 'var(--gray-600)' }}>{t('stats.total')}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', height: 18, borderRadius: 9, overflow: 'hidden', marginTop: 16, background: '#e5e7eb' }}>
                  <div style={{ width: `${malePct}%`, background: '#2563eb' }} title={`Hommes ${malePct}%`} />
                  <div style={{ width: `${femalePct}%`, background: '#db2777' }} title={`Femmes ${femalePct}%`} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '.8rem', color: 'var(--gray-600)', marginTop: 4 }}>
                  <span>Hommes {malePct}%</span>
                  <span>Femmes {femalePct}%</span>
                </div>
              </div>
            )}

            {isBureau && (
              <div className="card mb-24">
                {!showForm ? (
                  <button className="btn" onClick={() => setShowForm(true)}>➕ {t('stats.add')}</button>
                ) : (
                  <form onSubmit={create} style={{ display: 'grid', gap: 10, maxWidth: 420 }}>
                    <h3>{t('stats.add_title')}</h3>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <div className="form-group" style={{ flex: 1 }}>
                        <label>{t('stats.year')}</label>
                        <input type="number" min={2000} max={2100} required value={year} onChange={(e) => setYear(e.target.value)} />
                      </div>
                      <div className="form-group" style={{ flex: 1 }}>
                        <label>{t('stats.half')}</label>
                        <select value={half} onChange={(e) => setHalf(e.target.value)}>
                          <option value="1">S1</option>
                          <option value="2">S2</option>
                        </select>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <div className="form-group" style={{ flex: 1 }}>
                        <label>👨 {t('stats.male')}</label>
                        <input type="number" min={0} required value={male} onChange={(e) => setMale(e.target.value)} />
                      </div>
                      <div className="form-group" style={{ flex: 1 }}>
                        <label>👩 {t('stats.female')}</label>
                        <input type="number" min={0} required value={female} onChange={(e) => setFemale(e.target.value)} />
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn" disabled={saving}>{saving ? '…' : t('stats.save')}</button>
                      <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>{t('stats.cancel')}</button>
                    </div>
                  </form>
                )}
              </div>
            )}

            <div className="card">
              <h3>{t('stats.history')}</h3>
              {rows.length === 0 ? (
                <p style={{ color: 'var(--gray-600)' }}>{t('stats.empty')}</p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.9rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                      <th style={{ padding: 8, textAlign: 'left' }}>{t('stats.half')}</th>
                      <th style={{ padding: 8, textAlign: 'right' }}>👨 {t('stats.male')}</th>
                      <th style={{ padding: 8, textAlign: 'right' }}>👩 {t('stats.female')}</th>
                      <th style={{ padding: 8, textAlign: 'right' }}>{t('stats.total')}</th>
                      {isBureau && <th style={{ padding: 8 }} />}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr key={r.id} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                        <td style={{ padding: 8 }}>{semesterLabel(r.semester)}</td>
                        {editId === r.id ? (
                          <>
                            <td style={{ padding: 8 }}>
                              <input type="number" min={0} style={{ width: 70 }} value={editMale} onChange={(e) => setEditMale(e.target.value)} />
                            </td>
                            <td style={{ padding: 8 }}>
                              <input type="number" min={0} style={{ width: 70 }} value={editFemale} onChange={(e) => setEditFemale(e.target.value)} />
                            </td>
                            <td style={{ padding: 8, textAlign: 'right' }}>{r.total}</td>
                            <td style={{ padding: 8, textAlign: 'right', whiteSpace: 'nowrap' }}>
                              <button className="btn" style={{ marginRight: 6 }} onClick={() => saveEdit(r.id)}>✓</button>
                              <button className="btn btn-secondary" onClick={() => setEditId(null)}>✕</button>
                            </td>
                          </>
                        ) : (
                          <>
                            <td style={{ padding: 8, textAlign: 'right' }}>{r.male_count}</td>
                            <td style={{ padding: 8, textAlign: 'right' }}>{r.female_count}</td>
                            <td style={{ padding: 8, textAlign: 'right' }}>{r.total}</td>
                            {isBureau && (
                              <td style={{ padding: 8, textAlign: 'right', whiteSpace: 'nowrap' }}>
                                <button
                                  className="btn btn-secondary"
                                  style={{ marginRight: 6 }}
                                  onClick={() => { setEditId(r.id); setEditMale(String(r.male_count)); setEditFemale(String(r.female_count)) }}
                                >
                                  ✏️
                                </button>
                                <button className="btn btn-secondary" onClick={() => remove(r.id)}>🗑️</button>
                              </td>
                            )}
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </div>
      <Footer />
    </>
  )
}
