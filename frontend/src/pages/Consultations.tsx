import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import Footer from '../components/Footer'
import * as api from '../api/client'

const CATEGORIES: Record<string, string> = {
  conditions_travail: 'Conditions de travail',
  reglement_interieur: 'Règlement intérieur',
  temps_travail: 'Temps de travail',
  pension: 'Régime de pension',
  formation: 'Plan de formation continue',
  reclassement: 'Reclassement interne',
  licenciements_collectifs: 'Licenciements collectifs',
  transfert: "Transfert d'entreprise",
  interimaire: "Recours à l'intérim",
  oeuvres_sociales: 'Œuvres sociales',
  statistiques_sexe: 'Statistiques ventilées par sexe',
  teletravail: 'Télétravail / droit à la déconnexion',
  autre: 'Autre',
}

const STATUS_LABELS: Record<string, string> = {
  requested: '⏳ En attente de réponse',
  response_received: '✅ Réponse reçue',
  closed: '🔒 Clôturée',
}

const STATUS_COLORS: Record<string, string> = {
  requested: '#b45309',
  response_received: '#047857',
  closed: '#6b7280',
}

export default function Consultations() {
  const { t } = useT()
  const { user, token } = useAuth()
  const [rows, setRows] = useState<api.Consultation[]>([])
  const [stats, setStats] = useState<api.ConsultationStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [saving, setSaving] = useState(false)
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('conditions_travail')
  const [description, setDescription] = useState('')
  const [due, setDue] = useState('')
  const [respondId, setRespondId] = useState<number | null>(null)
  const [response, setResponse] = useState('')

  const isBureau = user?.delegue_role === 'president' || user?.delegue_role === 'vice_president' || user?.delegue_role === 'secretaire' || user?.role === 'admin'

  async function load() {
    try {
      const [r, s] = await Promise.all([api.listConsultations(), api.getConsultationStats()])
      setRows(r)
      setStats(s)
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
      await api.createConsultation({ title, category, description: description || undefined, response_due: due ? new Date(due + 'T00:00:00').toISOString() : undefined })
      setTitle(''); setDescription(''); setDue(''); setShowForm(false)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function recordResponse(id: number) {
    if (!response.trim()) return
    setSaving(true)
    try {
      await api.updateConsultation(id, { status: 'response_received', direction_response: response })
      setRespondId(null); setResponse(''); await load()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function closeConsultation(id: number) {
    try {
      await api.updateConsultation(id, { status: 'closed' })
      await load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  async function remove(id: number) {
    if (!confirm('Supprimer cette consultation ?')) return
    try {
      await api.deleteConsultation(id)
      await load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  const fmtDate = (iso: string | null) => iso ? new Date(iso).toLocaleDateString() : '—'
  const isOverdue = (c: api.Consultation) => c.status === 'requested' && c.response_due && new Date(c.response_due) < new Date()

  return (
    <>
      <NavBar />
      <div className="container">
        <div className="card">
          <h2>📋 {t('consultations.title')}</h2>
          <p className="text-muted" style={{ marginTop: 8, lineHeight: 1.5 }}>
            Suivi des consultations de la délégation avec la direction (art. L.414-3 du Code du travail) :
            avis et propositions sur les conditions de travail, le règlement intérieur, le temps de travail,
            la formation, ainsi que les informations/consultations préalables (licenciements collectifs, transferts, intérim).
            La direction doit répondre de manière motivée.
          </p>

          {stats && (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '16px 0' }}>
              <span className="badge" style={{ background: '#e2e8f0', color: '#1e293b' }}>Total : {stats.total}</span>
              <span className="badge" style={{ background: '#fef3c7', color: '#92400e' }}>En attente : {stats.pending}</span>
              {stats.overdue > 0 && <span className="badge" style={{ background: '#fee2e2', color: '#b91c1c', fontWeight: 700 }}>⚠️ Échéance dépassée : {stats.overdue}</span>}
              <span className="badge" style={{ background: '#d1fae5', color: '#065f46' }}>Réponses reçues : {stats.received}</span>
              <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>Clôturées : {stats.closed}</span>
            </div>
          )}

          {err && <p className="error-msg" style={{ color: 'var(--red)' }}>{err}</p>}

          {isBureau && (
            <button className="btn btn-primary" onClick={() => setShowForm(!showForm)} style={{ marginBottom: 16 }}>
              {showForm ? '✕ Fermer' : '➕ Nouvelle consultation'}
            </button>
          )}

          {showForm && isBureau && (
            <form onSubmit={create} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 20, background: '#f8fafc' }}>
              <div className="form-group">
                <label>Sujet de la consultation *</label>
                <input className="form-control" value={title} onChange={e => setTitle(e.target.value)} required minLength={3} maxLength={300} placeholder="Ex. : Révision du règlement intérieur" />
              </div>
              <div className="form-group">
                <label>Domaine (art. L.414-3)</label>
                <select className="form-control" value={category} onChange={e => setCategory(e.target.value)}>
                  {Object.entries(CATEGORIES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Description / demande</label>
                <textarea className="form-control" value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Précisions sur l'objet de la consultation…" />
              </div>
              <div className="form-group">
                <label>Date limite de réponse (optionnel — le règlement intérieur est fixé à 2 mois par la loi)</label>
                <input type="date" className="form-control" value={due} onChange={e => setDue(e.target.value)} />
              </div>
              <button className="btn btn-primary" disabled={saving}>{saving ? 'Enregistrement…' : 'Créer la consultation'}</button>
            </form>
          )}

          {loading ? (
            <div className="spinner" />
          ) : rows.length === 0 ? (
            <p className="text-muted">Aucune consultation pour le moment.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {rows.map(c => (
                <div key={c.id} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 14, background: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <strong>{c.title}</strong>
                    <span className="badge" style={{ background: STATUS_COLORS[c.status] || '#6b7280', color: '#fff' }}>
                      {STATUS_LABELS[c.status] || c.status}
                    </span>
                  </div>
                  <div style={{ marginTop: 6, fontSize: '.85rem', color: '#475569' }}>
                    {CATEGORIES[c.category] || c.category}
                    {c.created_by_name ? ` · par ${c.created_by_name}` : ''}
                    {' · demandée le '}{fmtDate(c.requested_at)}
                    {c.response_due && (
                      <span style={{ color: isOverdue(c) ? 'var(--red)' : undefined, fontWeight: isOverdue(c) ? 700 : 400 }}>
                        {' · réponse attendue avant le '}{fmtDate(c.response_due)}
                        {isOverdue(c) ? ' ⚠️' : ''}
                      </span>
                    )}
                  </div>
                  {c.description && <p style={{ marginTop: 8, fontSize: '.9rem' }}>{c.description}</p>}
                  {c.direction_response && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: '#ecfdf5', borderRadius: 6, fontSize: '.9rem', borderLeft: '3px solid #10b981' }}>
                      <strong>Réponse de la direction</strong> ({fmtDate(c.direction_responded_at)}) : {c.direction_response}
                    </div>
                  )}
                  {isBureau && c.status !== 'closed' && (
                    <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {respondId === c.id ? (
                        <>
                          <textarea className="form-control" rows={2} style={{ flex: 1, minWidth: 220 }} value={response} onChange={e => setResponse(e.target.value)} placeholder="Réponse motivée de la direction…" />
                          <button className="btn btn-primary" disabled={saving || !response.trim()} onClick={() => recordResponse(c.id)}>Enregistrer</button>
                          <button className="btn" onClick={() => { setRespondId(null); setResponse('') }}>Annuler</button>
                        </>
                      ) : (
                        <>
                          <button className="btn" onClick={() => setRespondId(c.id)}>✍️ Enregistrer la réponse</button>
                          {c.direction_response && <button className="btn" onClick={() => closeConsultation(c.id)}>🔒 Clôturer</button>}
                          {c.status === 'requested' && <button className="btn" style={{ color: 'var(--red)' }} onClick={() => remove(c.id)}>🗑️ Supprimer</button>}
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
      <Footer />
    </>
  )
}
