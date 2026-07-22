import { useEffect, useState, type FormEvent } from 'react'
import NavBar from '../components/NavBar'
import { useAuth } from '../hooks/useAuth'

interface TimeEntry {
  id: number; date: string; hours: number; description: string | null; category: string
}

const CATEGORIES = [
  { value: 'reunion', label: '🤝 Réunion' },
  { value: 'formation', label: '📚 Formation' },
  { value: 'tournee', label: '🔍 Tournée contrôle' },
  { value: 'administratif', label: '📋 Administratif' },
  { value: 'autre', label: '📌 Autre' },
]

export default function TimeTracking() {
  const { token, organization } = useAuth()
  const weeklyPool = organization?.weekly_credit_hours
  const [entries, setEntries] = useState<TimeEntry[]>([])
  const [summary, setSummary] = useState({ month: '', total_hours: 0, credit_hours: 20, remaining: 20 })
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), hours: '', description: '', category: 'reunion' })
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [filterMonth, setFilterMonth] = useState(new Date().toISOString().slice(0, 7))

  const h = { Authorization: `Bearer ${token}` }

  useEffect(() => { loadData() }, [filterMonth])

  async function loadData() {
    try {
      const [eRes, sRes] = await Promise.all([
        fetch(`/api/time?month=${filterMonth}`, { headers: h }),
        fetch(`/api/time/summary?month=${filterMonth}`, { headers: h }),
      ])
      setEntries(await eRes.json())
      setSummary(await sRes.json())
    } catch { /* */ }
  }

  async function addEntry(e: FormEvent) {
    e.preventDefault(); setErr(null); setLoading(true)
    try {
      const res = await fetch('/api/time', {
        method: 'POST', headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, hours: parseFloat(form.hours) }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      setMsg('Heures ajoutées ✅')
      setForm({ date: new Date().toISOString().slice(0, 10), hours: '', description: '', category: 'reunion' })
      loadData()
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  async function deleteEntry(id: number) {
    try { await fetch(`/api/time/${id}`, { method: 'DELETE', headers: h }); loadData() } catch { /* */ }
  }

  const formatDate = (d: string) => new Date(d).toLocaleDateString('fr-LU')
  const catLabel = (c: string) => CATEGORIES.find(x => x.value === c)?.label || c

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-16" style={{ background: summary.remaining < 0 ? '#fff5f5' : '#f0fff4', padding: 16, display: 'flex', justifyContent: 'space-around', fontSize: '.9rem' }}>
          <span>📅 {summary.month}</span>
          <span>👤 <strong>{summary.total_hours}h</strong> / {summary.credit_hours}h perso</span>
          {weeklyPool != null && <span>🏢 Crédit délégation : <strong>{weeklyPool}h/sem</strong> (~{weeklyPool * 4}h/mois)</span>}
          <span style={{ color: summary.remaining < 0 ? 'var(--red)' : '#276749', fontWeight: 600 }}>
            {summary.remaining < 0 ? `-${Math.abs(summary.remaining)}h dépassé` : `${summary.remaining}h restant`}
          </span>
        </div>

        <div className="card mb-24">
          <h2>⏱️ Ajouter des heures</h2>
          <form onSubmit={addEntry}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
              <div className="form-group"><label>Date</label><input type="date" value={form.date} onChange={e => setForm(p => ({ ...p, date: e.target.value }))} required /></div>
              <div className="form-group"><label>Heures</label><input type="number" step="0.5" min="0.5" max="24" value={form.hours} onChange={e => setForm(p => ({ ...p, hours: e.target.value }))} required placeholder="2.5" /></div>
              <div className="form-group"><label>Catégorie</label>
                <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))}
                  style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                  {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group"><label>Description</label><input value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} placeholder="Réunion avec la direction..." /></div>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <div className="spinner" /> : 'Ajouter'}
            </button>
          </form>
        </div>

        <div className="card mb-24">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2>📋 Historique</h2>
            <input type="month" value={filterMonth} onChange={e => setFilterMonth(e.target.value)}
              style={{ padding: '6px 10px', border: '1.5px solid var(--gray-300)', borderRadius: 'var(--radius)' }} />
          </div>
          {entries.length === 0 ? (
            <p style={{ color: 'var(--gray-600)', textAlign: 'center', padding: 20 }}>Aucune entrée ce mois-ci.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
              <thead><tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                <th style={{ padding: '6px 8px', textAlign: 'left' }}>Date</th>
                <th style={{ padding: '6px 8px', textAlign: 'left' }}>Heures</th>
                <th style={{ padding: '6px 8px', textAlign: 'left' }}>Catégorie</th>
                <th style={{ padding: '6px 8px', textAlign: 'left' }}>Description</th>
                <th></th>
              </tr></thead>
              <tbody>
                {entries.map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                    <td style={{ padding: '6px 8px' }}>{formatDate(e.date)}</td>
                    <td style={{ padding: '6px 8px', fontWeight: 600 }}>{e.hours}h</td>
                    <td style={{ padding: '6px 8px' }}>{catLabel(e.category)}</td>
                    <td style={{ padding: '6px 8px', color: 'var(--gray-600)' }}>{e.description || '—'}</td>
                    <td style={{ padding: '6px 8px' }}>
                      <button onClick={() => deleteEntry(e.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '.8rem' }}>🗑️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  )
}
