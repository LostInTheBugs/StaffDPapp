import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import NavBar from '../components/NavBar'
import * as api from '../api/client'

interface Member {
  id: number; full_name: string; role: string; delegue_status: string; delegue_role: string
}

export default function EditOrganization() {
  const { user, organization, setAuth, token } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'

  const [form, setForm] = useState({
    name: organization?.name || '',
    company_name: organization?.company_name || '',
    employee_count: organization?.employee_count || 15,
    mandate_end_date: organization?.mandate_end_date || '',
  })
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [members, setMembers] = useState<Member[]>([])

  useEffect(() => {
    if (!isAdmin) { navigate('/dashboard'); return }
    loadMembers()
  }, [])

  async function loadMembers() {
    try {
      const res = await fetch('/api/organization/members', { headers: { Authorization: `Bearer ${token}` } })
      setMembers(await res.json())
    } catch { /* */ }
  }

  async function updateOrg(e: FormEvent) {
    e.preventDefault(); setErr(null)
    if (form.employee_count < 15) { setErr('Minimum 15 salariés'); return }
    try {
      const data: any = { ...form }
      if (!data.mandate_end_date) delete data.mandate_end_date
      const updated = await api.updateOrganization(data)
      setAuth(token!, user!, updated)
      setMsg('Organisation mise à jour ✅')
    } catch (e: any) { setErr(e.message) }
  }

  async function toggleRole(member: Member) {
    if (!isAdmin) return
    const newRole = member.role === 'admin' ? 'member' : 'admin'
    try {
      await fetch(`/api/organization/members/${member.id}/role`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      setMembers(prev => prev.map(m => m.id === member.id ? { ...m, role: newRole } : m))
    } catch { /* */ }
  }

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <h2>🏢 Mon organisation</h2>
          <form onSubmit={updateOrg}>
            <div className="form-group"><label>Nom de la délégation *</label><input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} required /></div>
            <div className="form-group"><label>Nom officiel de l'entreprise</label><input value={form.company_name} onChange={e => setForm(p => ({ ...p, company_name: e.target.value }))} /></div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div className="form-group"><label>Effectif *</label><input type="number" min={15} value={form.employee_count} onChange={e => setForm(p => ({ ...p, employee_count: parseInt(e.target.value) || 15 }))} required /></div>
              <div className="form-group"><label>Date de fin de mandat</label><input type="date" value={form.mandate_end_date} onChange={e => setForm(p => ({ ...p, mandate_end_date: e.target.value }))} /></div>
            </div>
            <button type="submit" className="btn btn-primary">Enregistrer</button>
          </form>
        </div>

        <div className="card mb-24">
          <h2>👥 Gestion des administrateurs</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>
            Les administrateurs peuvent modifier l'organisation et gérer les rôles.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
            <thead><tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
              <th style={{ padding: '8px', textAlign: 'left' }}>Membre</th>
              <th style={{ padding: '8px', textAlign: 'left' }}>Statut</th>
              <th style={{ padding: '8px', textAlign: 'left' }}>Rôle</th>
              <th style={{ padding: '8px' }}></th>
            </tr></thead>
            <tbody>
              {members.map(m => (
                <tr key={m.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                  <td style={{ padding: '8px' }}>{m.full_name}</td>
                  <td style={{ padding: '8px' }}>{m.delegue_status} / {m.delegue_role}</td>
                  <td style={{ padding: '8px' }}>
                    <span style={{
                      background: m.role === 'admin' ? '#ebf8ff' : 'var(--gray-100)',
                      color: m.role === 'admin' ? 'var(--blue)' : 'var(--gray-600)',
                      padding: '2px 10px', borderRadius: 4, fontWeight: 600, fontSize: '.8rem'
                    }}>
                      {m.role === 'admin' ? '👑 Admin' : 'Membre'}
                    </span>
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>
                    <button onClick={() => toggleRole(m)}
                      style={{
                        background: m.role === 'admin' ? 'var(--red)' : 'var(--blue)',
                        color: '#fff', border: 'none', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: '.75rem'
                      }}>
                      {m.role === 'admin' ? 'Rétrograder' : 'Promouvoir admin'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
