import { useEffect, useMemo, useState } from 'react'
import NavBar from '../components/NavBar'
import Footer from '../components/Footer'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'

const CATEGORY_LABELS: Record<string, string> = {
  visite: '🛡️ Visite / tournée de contrôle',
  enquete: '🔍 Enquête',
  formation: '🎓 Formation',
  signalement: '⚠️ Signalement',
  action: '⚡ Action',
  sensibilisation: '📣 Sensibilisation',
  autre: '🗂️ Autre',
}

const DOMAIN_LABELS: Record<string, string> = {
  securite_sante: '🛡️ Sécurité & santé (L.414-14)',
  egalite: '⚖️ Égalité (L.414-15)',
}

interface ActivityRow {
  id: number
  user_id: number
  name: string
  domain: string
  category: string
  description: string
  date: string
  created_by_id: number
}

export default function DelegateActivities() {
  const { t } = useT()
  const { user } = useAuth()

  const [rows, setRows] = useState<ActivityRow[]>([])
  const [members, setMembers] = useState<Array<{ id: number; first_name: string; last_name: string; is_delegue_securite_sante: boolean; is_delegue_egalite: boolean }>>([])
  const [year, setYear] = useState(String(new Date().getFullYear()))
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Formulaire
  const [formUser, setFormUser] = useState('')
  const [formDomain, setFormDomain] = useState('securite_sante')
  const [formCategory, setFormCategory] = useState('visite')
  const [formDate, setFormDate] = useState(new Date().toISOString().slice(0, 10))
  const [formDesc, setFormDesc] = useState('')

  const isBureau = user?.role === 'admin' || ['president', 'vice_president', 'secretaire'].includes(user?.delegue_role || '')
  const myDesignations = useMemo(() => {
    if (!user) return []
    const d: string[] = []
    if (user.is_delegue_securite_sante) d.push('securite_sante')
    if (user.is_delegue_egalite) d.push('egalite')
    return d
  }, [user])
  const canWrite = isBureau || myDesignations.length > 0

  const designatedMembers = useMemo(() => members.filter(m => m.is_delegue_securite_sante || m.is_delegue_egalite), [members])

  async function load() {
    try {
      const tok = localStorage.getItem('token')
      const h = { Authorization: 'Bearer ' + tok }
      const [actsRes, memsRes] = await Promise.all([
        fetch(`/api/delegate-activities?year=${parseInt(year, 10)}`, { headers: h }),
        fetch('/api/organization/members', { headers: h }),
      ])
      if (!actsRes.ok || !memsRes.ok) throw new Error('Erreur de chargement')
      setRows(await actsRes.json())
      setMembers(await memsRes.json())
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  useEffect(() => { load() }, [year]) // eslint-disable-line react-hooks/exhaustive-deps

  // Domaines proposés dans le formulaire
  const formDomains = useMemo(() => {
    if (isBureau) return ['securite_sante', 'egalite']
    return myDesignations
  }, [isBureau, myDesignations])

  useEffect(() => {
    if (formDomains.length > 0 && !formDomains.includes(formDomain)) {
      setFormDomain(formDomains[0])
      setFormCategory(formDomains[0] === 'securite_sante' ? 'visite' : 'action')
    }
  }, [formDomains, formDomain])

  const formCategories = formDomain === 'securite_sante'
    ? ['visite', 'enquete', 'formation', 'signalement', 'autre']
    : ['action', 'sensibilisation', 'formation', 'signalement', 'autre']

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setBusy(true)
    try {
      const targetId = isBureau ? parseInt(formUser, 10) : user!.id
      const res = await fetch('/api/delegate-activities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + localStorage.getItem('token') },
        body: JSON.stringify({
          user_id: targetId,
          domain: formDomain,
          category: formCategory,
          description: formDesc,
          date: `${formDate}T09:00:00`,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        throw new Error(data?.detail || 'Erreur lors de l\'enregistrement')
      }
      setFormDesc('')
      await load()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm(t('delegate_activities.delete_confirm'))) return
    try {
      const res = await fetch(`/api/delegate-activities/${id}`, {
        method: 'DELETE',
        headers: { Authorization: 'Bearer ' + localStorage.getItem('token') },
      })
      if (!res.ok) throw new Error('Erreur lors de la suppression')
      await load()
    } catch (e) {
      setErr((e as Error).message)
    }
  }

  const canDelete = (r: ActivityRow) => isBureau || r.created_by_id === user?.id

  return (
    <>
      <NavBar />
      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <h2>🛡️ {t('delegate_activities.title')}</h2>
          <select
            value={year}
            onChange={(e) => setYear(e.target.value)}
            style={{ padding: '6px 8px', fontSize: '.85rem', borderRadius: 6, border: '1px solid var(--gray-300)' }}
            aria-label="Année"
          >
            {Array.from({ length: 5 }, (_, i) => String(new Date().getFullYear() - i)).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <p style={{ color: 'var(--gray-600)', marginBottom: 16 }}>
          {t('delegate_activities.subtitle')}
        </p>

        {err && <div className="error-msg" style={{ marginBottom: 12 }}>⚠️ {err}</div>}

        {canWrite && (
          <div className="card" style={{ marginBottom: 20 }}>
            <h3>{t('delegate_activities.add_title')}</h3>
            <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 12 }}>
              {isBureau && (
                <div className="form-group">
                  <label>{t('delegate_activities.delegate')}</label>
                  <select value={formUser} onChange={(e) => setFormUser(e.target.value)} required>
                    <option value="">—</option>
                    {designatedMembers.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.first_name} {m.last_name}
                        {m.is_delegue_securite_sante ? ' 🛡️' : ''}{m.is_delegue_egalite ? ' ⚖️' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-group">
                <label>{t('delegate_activities.domain')}</label>
                <select value={formDomain} onChange={(e) => { setFormDomain(e.target.value); setFormCategory(e.target.value === 'securite_sante' ? 'visite' : 'action') }}>
                  {formDomains.map(d => (
                    <option key={d} value={d}>{DOMAIN_LABELS[d]}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>{t('delegate_activities.category')}</label>
                <select value={formCategory} onChange={(e) => setFormCategory(e.target.value)}>
                  {formCategories.map(c => (
                    <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>{t('delegate_activities.date')}</label>
                <input type="date" value={formDate} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setFormDate(e.target.value)} required />
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label>{t('delegate_activities.description')}</label>
                <textarea
                  value={formDesc}
                  onChange={(e) => setFormDesc(e.target.value)}
                  required
                  minLength={3}
                  rows={2}
                  placeholder={t('delegate_activities.description_placeholder')}
                />
              </div>
              <div>
                <button type="submit" className="btn btn-primary" disabled={busy || (isBureau && !formUser) || !formDesc.trim()}>
                  {busy ? '…' : '+ ' + t('delegate_activities.add_btn')}
                </button>
              </div>
            </form>
          </div>
        )}

        {rows.length === 0 ? (
          <p style={{ color: 'var(--gray-600)' }}>{t('delegate_activities.empty')}</p>
        ) : (
          <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--gray-100)', textAlign: 'left' }}>
                <th style={{ padding: 8 }}>{t('delegate_activities.date')}</th>
                <th style={{ padding: 8 }}>{t('delegate_activities.delegate')}</th>
                <th style={{ padding: 8 }}>{t('delegate_activities.domain')}</th>
                <th style={{ padding: 8 }}>{t('delegate_activities.category')}</th>
                <th style={{ padding: 8 }}>{t('delegate_activities.description')}</th>
                <th style={{ padding: 8 }}></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                  <td style={{ padding: 8, whiteSpace: 'nowrap' }}>{new Date(r.date).toLocaleDateString('fr-LU')}</td>
                  <td style={{ padding: 8, fontWeight: 600 }}>{r.name}</td>
                  <td style={{ padding: 8 }}>{DOMAIN_LABELS[r.domain] || r.domain}</td>
                  <td style={{ padding: 8 }}>{CATEGORY_LABELS[r.category] || r.category}</td>
                  <td style={{ padding: 8 }}>{r.description}</td>
                  <td style={{ padding: 8 }}>
                    {canDelete(r) && (
                      <button
                        className="btn"
                        style={{ padding: '4px 8px', fontSize: '.8rem', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca' }}
                        onClick={() => handleDelete(r.id)}
                      >
                        🗑️
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Footer />
    </>
  )
}
