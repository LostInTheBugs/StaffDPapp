import { useEffect, useState, type FormEvent } from 'react'
import NavBar from '../components/NavBar'
import { useAuth } from '../hooks/useAuth'

interface Meeting {
  id: number; title: string; date: string; location: string | null; status: string
  direction_invited: boolean
  created_by_name: string | null; points: { description: string }[]
  invitees: { id: number; user_id: number; user_name: string | null; status: string }[]
}

interface Member { id: number; full_name: string; delegue_status: string }

export default function Meetings() {
  const { token, organization } = useAuth()
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [members, setMembers] = useState<Member[]>([])
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', date: '', location: '', direction_invited: false, points: [''] })
  const [inviteeIds, setInviteeIds] = useState<number[]>([])
  const [stats, setStats] = useState({ total: 0, with_direction: 0, min_required: 6, min_with_direction: 3 })
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const h = { Authorization: `Bearer ${token}` }

  useEffect(() => { loadMeetings(); loadMembers(); loadStats() }, [])
  async function loadStats() {
    try { const r = await fetch('/api/meetings/stats', { headers: h }); setStats(await r.json()) } catch { /* */ }
  }

  async function loadMeetings() {
    try { const r = await fetch('/api/meetings', { headers: h }); setMeetings(await r.json()) } catch { /* */ }
  }
  async function loadMembers() {
    try { const r = await fetch('/api/organization/members', { headers: h }); setMembers(await r.json()) } catch { /* */ }
  }

  function toggleInvitee(id: number) {
    setInviteeIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  function updatePoint(i: number, val: string) {
    setForm(prev => { const p = [...prev.points]; p[i] = val; return { ...prev, points: p } })
  }

  async function createMeeting(e: FormEvent) {
    e.preventDefault(); setErr(null)
    const minInvites = organization?.required_titulaires || 0
    if (inviteeIds.length < minInvites) {
      setErr(`Minimum ${minInvites} invité(s) requis (nombre de titulaires). Les suppléants peuvent remplacer les titulaires absents.`)
      return
    }
    setLoading(true)
    try {
      const res = await fetch('/api/meetings', {
        method: 'POST', headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: form.title, date: new Date(form.date).toISOString(), location: form.location || null,
          direction_invited: form.direction_invited,
          points: form.points.filter(p => p.trim()).map((p, i) => ({ description: p, order: i })),
          invitee_ids: inviteeIds,
        }),
      })
      if (!res.ok) throw new Error((await res.json()).detail)
      setMsg('Réunion créée ✅')
      setShowForm(false)
      setForm({ title: '', date: '', location: '', direction_invited: false, points: [''] })
      setInviteeIds([])
      loadMeetings()
    } catch (e: any) { setErr(e.message) }
    finally { setLoading(false) }
  }

  async function respond(meetingId: number, status: string) {
    try {
      await fetch(`/api/meetings/${meetingId}/respond`, {
        method: 'POST', headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      loadMeetings()
    } catch { /* */ }
  }

  async function deleteMeeting(id: number) {
    if (!confirm('Supprimer cette réunion ?')) return
    try { await fetch(`/api/meetings/${id}`, { method: 'DELETE', headers: h }); loadMeetings() } catch { /* */ }
  }

  const formatDate = (d: string) => new Date(d).toLocaleString('fr-LU', { dateStyle: 'long', timeStyle: 'short' })

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
            <h2>📅 Réunions</h2>
            <button onClick={async () => {
              const opening = !showForm
              setShowForm(opening)
              if (opening) {
                // Reload members for fresh list, then auto-select titulaires
                try {
                  const r = await fetch('/api/organization/members', { headers: h })
                  const fresh = await r.json()
                  setMembers(fresh)
                  const titulaires = fresh.filter((m: Member) => m.delegue_status === 'titulaire')
                  setInviteeIds(titulaires.map((m: Member) => parseInt(m.id.toString())))
                } catch { /* */ }
              }
            }} className="btn btn-primary" style={{ width:'auto', padding:'8px 16px' }}>
              {showForm ? 'Annuler' : '+ Nouvelle réunion'}
            </button>
          </div>

          {showForm && (
            <form onSubmit={createMeeting} style={{ marginTop: 20, borderTop:'1px solid var(--gray-300)', paddingTop: 20 }}>
              <div className="form-group"><label>Titre *</label><input value={form.title} onChange={e => setForm(p => ({ ...p, title: e.target.value }))} required autoFocus /></div>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
                <div className="form-group"><label>Date *</label><input type="datetime-local" value={form.date} onChange={e => setForm(p => ({ ...p, date: e.target.value }))} required
                  min={form.direction_invited ? new Date(Date.now() + 7*86400000).toISOString().slice(0,16) : undefined} /></div>
                <div className="form-group"><label>Lieu</label><input value={form.location} onChange={e => setForm(p => ({ ...p, location: e.target.value }))} /></div>
              </div>

              <label style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16, cursor:'pointer', background: form.direction_invited ? '#fff5f5' : 'var(--gray-50)', padding:'10px 14px', borderRadius:'var(--radius)' }}>
                <input type="checkbox" checked={form.direction_invited} onChange={e => setForm(p => ({ ...p, direction_invited: e.target.checked }))} />
                <span style={{ fontWeight:600, fontSize:'.9rem' }}>🏢 Inviter la direction</span>
                <small style={{ color:'var(--gray-600)' }}>(la réunion sera planifiée à J+5 ouvrables minimum)</small>
              </label>

              <label style={{ fontWeight:600, fontSize:'.88rem', display:'block', marginBottom:4 }}>Points à l'ordre du jour</label>
              {form.points.map((p, i) => (
                <div key={i} style={{ display:'flex', gap:8, marginBottom:8 }}>
                  <span style={{ paddingTop:10, color:'var(--gray-600)', fontSize:'.8rem' }}>{i + 1}.</span>
                  <input value={p} onChange={e => updatePoint(i, e.target.value)} placeholder={`Point ${i + 1}`}
                    style={{ flex:1, padding:'8px 12px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)' }} />
                  {form.points.length > 1 && (
                    <button type="button" onClick={() => setForm(prev => ({ ...prev, points: prev.points.filter((_, j) => j !== i) }))}
                      style={{ background:'none', border:'none', color:'var(--red)', cursor:'pointer', fontSize:'1.2rem' }}>×</button>
                  )}
                </div>
              ))}
              <button type="button" onClick={() => setForm(prev => ({ ...prev, points: [...prev.points, ''] }))}
                className="link mb-16" style={{ background:'none', border:'none', cursor:'pointer', fontSize:'.85rem' }}>
                + Ajouter un point
              </button>

              <label style={{ fontWeight:600, fontSize:'.88rem', display:'block', marginBottom:8 }}>Inviter les membres</label>
              <div style={{ display:'flex', flexWrap:'wrap', gap:6, marginBottom:16 }}>
                {members.map(m => (
                  <label key={m.id} style={{ cursor:'pointer', padding:'6px 12px', borderRadius:6, border:`1.5px solid ${inviteeIds.includes(m.id) ? 'var(--blue)' : 'var(--gray-300)'}`, background: inviteeIds.includes(m.id) ? '#ebf8ff' : '#fff', fontSize:'.85rem', display:'flex', alignItems:'center', gap:6 }}>
                    <input type="checkbox" checked={inviteeIds.includes(m.id)} onChange={() => toggleInvitee(m.id)} style={{ display:'none' }} />
                    {m.full_name}
                  </label>
                ))}
              </div>

              <button type="submit" className="btn btn-primary" disabled={loading}>
                {loading ? <div className="spinner" /> : 'Créer la réunion'}
              </button>
            </form>
          )}
        </div>

        {meetings.length === 0 && !showForm && (
          <div className="card mb-24" style={{ textAlign:'center', color:'var(--gray-600)', padding:40 }}>
            Aucune réunion planifiée.
          </div>
        )}

        <div className="card mb-16" style={{ padding:16, background:'#f0fff4', display:'flex', gap:24, fontSize:'.85rem' }}>
          <span>📅 <strong>{stats.total}</strong>/{stats.min_required} réunions cette année</span>
          <span>🏢 <strong>{stats.with_direction}</strong>/{stats.min_with_direction} avec la direction</span>
        </div>

        {meetings.map(m => (
          <div key={m.id} className="card mb-16" style={{ padding:24 }}>
            <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
              <div>
                <h3 style={{ marginBottom:4 }}>{m.title}</h3>
                <p style={{ color:'var(--gray-600)', fontSize:'.85rem' }}>
                  📅 {formatDate(m.date)} {m.location && `— 📍 ${m.location}`}
                </p>
                <p style={{ color:'var(--gray-600)', fontSize:'.8rem' }}>
                  Créé par {m.created_by_name || '?'} — {m.status}
                  {m.direction_invited && <span style={{ background:'#fff5f5', color:'#c53030', padding:'1px 6px', borderRadius:4, fontSize:'.7rem', fontWeight:700, marginLeft:6 }}>🏢 Direction invitée</span>}
                </p>

                {m.points.length > 0 && (
                  <div style={{ marginTop:12 }}>
                    <strong style={{ fontSize:'.85rem' }}>Ordre du jour :</strong>
                    <ol style={{ marginTop:4, paddingLeft:20, fontSize:'.85rem' }}>
                      {m.points.map((p, i) => <li key={i}>{p.description}</li>)}
                    </ol>
                  </div>
                )}

                {m.invitees.length > 0 && (
                  <div style={{ marginTop:12 }}>
                    <strong style={{ fontSize:'.85rem' }}>Invités :</strong>
                    <div style={{ display:'flex', flexWrap:'wrap', gap:4, marginTop:4 }}>
                      {m.invitees.map(inv => (
                        <span key={inv.id} style={{
                          fontSize:'.8rem', padding:'2px 8px', borderRadius:4,
                          background: inv.status === 'accepted' ? '#c6f6d5' : inv.status === 'declined' ? '#fed7d7' : '#fefcbf',
                          color: inv.status === 'accepted' ? '#276749' : inv.status === 'declined' ? '#9b2c2c' : '#975a16',
                        }}>
                          {inv.user_name || '?'} ({inv.status === 'accepted' ? '✅' : inv.status === 'declined' ? '❌' : '⏳'})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display:'flex', gap:8 }}>
                {/* Respond buttons for invitees */}
                {m.invitees.some(inv => inv.status === 'pending' && members.find(mb => mb.id === inv.user_id)) && (
                  <>
                    <button onClick={() => respond(m.id, 'accepted')}
                      style={{ background:'#c6f6d5', border:'none', color:'#276749', padding:'4px 10px', borderRadius:4, cursor:'pointer', fontSize:'.8rem' }}>✅ Participe</button>
                    <button onClick={() => respond(m.id, 'declined')}
                      style={{ background:'#fed7d7', border:'none', color:'#9b2c2c', padding:'4px 10px', borderRadius:4, cursor:'pointer', fontSize:'.8rem' }}>❌ Décline</button>
                  </>
                )}
                <button onClick={() => deleteMeeting(m.id)}
                  style={{ background:'none', border:'none', color:'var(--gray-600)', cursor:'pointer', fontSize:'.8rem' }}>🗑️</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
