import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import NavBar from '../components/NavBar'
import * as api from '../api/client'

interface Member {
  id: number; first_name: string; last_name: string; full_name: string
  delegue_status: string; delegue_role: string
  is_delegue_securite_sante: boolean; is_delegue_egalite: boolean
  role: string
}

export default function Organigramme() {
  const { user, organization, token } = useAuth()
  const [members, setMembers] = useState<Member[]>([])
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ delegue_status: 'titulaire', delegue_role: 'membre', email: '', first_name: '', last_name: '', is_delegue_securite_sante: false, is_delegue_egalite: false })
  const [inviteCode, setInviteCode] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { loadMembers() }, [])

  async function loadMembers() {
    try {
      const res = await fetch('/api/organization/members', { headers: { Authorization: `Bearer ${token}` } })
      setMembers(await res.json())
    } catch { /* */ }
  }

  const canInvite = user && (user.role === 'admin' || ['president', 'vice_president', 'secretaire'].includes(user.delegue_role))

  function openInvite(status: string, role: string) {
    setInviteForm({ delegue_status: status, delegue_role: role, email: '', first_name: '', last_name: '', is_delegue_securite_sante: false, is_delegue_egalite: false })
    setInviteCode(null); setError(null); setShowInvite(true)
  }

  async function sendInvite(e: React.FormEvent) {
    e.preventDefault(); setError(null)
    try {
      const inv = await api.createInvitation(inviteForm)
      setInviteCode(inv.code)
    } catch (err: any) { setError(err.message) }
  }

  function MemberCell({ member, status, role }: { member?: Member; status: string; role?: string }) {
    if (member) {
      return (
        <div style={{ background: '#ebf8ff', border: '2px solid #2b6cb0', borderRadius: 8, padding: '8px 10px', textAlign: 'center', minWidth: 110 }}>
          <div style={{ fontWeight: 600, fontSize: '.85rem' }}>{member.first_name} {member.last_name}</div>
          <div style={{ fontSize: '.7rem', color: '#4a5568' }}>{roleLabel(member.delegue_role)}</div>
        </div>
      )
    }
    if (canInvite) {
      return (
        <button onClick={() => openInvite(status, role || 'membre')}
          style={{ background: '#fff', border: '2px dashed #cbd5e0', borderRadius: 8, padding: '8px 10px', cursor: 'pointer', minWidth: 110, textAlign: 'center', color: '#a0aec0', fontSize: '.85rem' }}>
          + {status === 'employe' ? 'Désigner' : 'Inviter'}
        </button>
      )
    }
    return <div style={{ background: '#f7fafc', border: '2px dashed #e2e8f0', borderRadius: 8, padding: '8px 10px', minWidth: 110, textAlign: 'center', color: '#cbd5e0', fontSize: '.8rem' }}>—</div>
  }

  const statusLabel = (s: string) => api.DELEGUE_STATUS.find(r => r.value === s)?.label || s
  const roleLabel = (r: string) => api.DELEGUE_ROLES.find(x => x.value === r)?.label || r

  if (!organization) return <div className="dashboard"><div className="spinner" /></div>
  const n = organization.required_titulaires

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <div className="card mb-24">
          <h2>👥 Membres de la délégation</h2>

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Bureau</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>Président(e)</div>
              <MemberCell member={members.find(m => m.delegue_role === 'president')} status="titulaire" role="president" />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>Vice-président(e)</div>
              <MemberCell member={members.find(m => m.delegue_role === 'vice_president')} status="titulaire" role="vice_president" />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>Secrétaire</div>
              <MemberCell member={members.find(m => m.delegue_role === 'secretaire')} status="titulaire" role="secretaire" />
            </div>
          </div>

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Titulaires ({n})</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
            {Array.from({ length: n }, (_, i) => {
              const filled = members.filter(m => m.delegue_status === 'titulaire' && m.delegue_role === 'membre' && !['president','vice_president','secretaire'].includes(m.delegue_role))
              const m = filled[i]
              return <MemberCell key={`t${i}`} member={m} status="titulaire" />
            })}
          </div>

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Suppléants ({n})</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
            {Array.from({ length: n }, (_, i) => {
              const filled = members.filter(m => m.delegue_status === 'suppleant')
              const m = filled[i]
              return <MemberCell key={`s${i}`} member={m} status="suppleant" />
            })}
          </div>

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Désignations spéciales</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>🛡️ Sécurité/Santé</div>
              <MemberCell member={members.find(m => m.is_delegue_securite_sante)} status="employe" />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>⚖️ Égalité</div>
              <MemberCell member={members.find(m => m.is_delegue_egalite)} status="titulaire" />
            </div>
          </div>
        </div>

        {showInvite && (
          <div className="card mb-24">
            <h2>✉️ Inviter — {statusLabel(inviteForm.delegue_status)} / {roleLabel(inviteForm.delegue_role)}</h2>
            {error && <div className="error-msg">{error}</div>}
            {inviteCode ? (
              <div className="success-msg">
                Code d'invitation : <div className="invite-code mt-16">{inviteCode}</div>
                <button onClick={() => { setShowInvite(false); loadMembers() }} className="btn btn-primary mt-16">Fermer</button>
              </div>
            ) : (
              <form onSubmit={sendInvite}>
                <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
                  <div className="form-group"><label>Prénom *</label><input value={inviteForm.first_name} onChange={e => setInviteForm(p => ({ ...p, first_name: e.target.value }))} required autoFocus /></div>
                  <div className="form-group"><label>Nom *</label><input value={inviteForm.last_name} onChange={e => setInviteForm(p => ({ ...p, last_name: e.target.value }))} required /></div>
                </div>
                <div className="form-group"><label>Email *</label><input type="email" value={inviteForm.email} onChange={e => setInviteForm(p => ({ ...p, email: e.target.value }))} required /></div>
                <div style={{ display:'flex', gap:8 }}>
                  <button type="submit" className="btn btn-primary">Générer le code</button>
                  <button type="button" onClick={() => setShowInvite(false)} className="btn" style={{ background:'var(--gray-300)' }}>Annuler</button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </>
  )
}
