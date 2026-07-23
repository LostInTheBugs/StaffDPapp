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
  const [showDesignate, setShowDesignate] = useState<'securite_sante' | 'egalite' | null>(null)
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

  function openInvite(status: string, role: string, isSecu = false, isEgal = false) {
    setInviteForm({ delegue_status: status, delegue_role: role, email: '', first_name: '', last_name: '', is_delegue_securite_sante: isSecu, is_delegue_egalite: isEgal })
    setInviteCode(null); setError(null); setShowInvite(true)
  }

  async function sendInvite(e: React.FormEvent) {
    e.preventDefault()
    try {
      const inv = await api.createInvitation(inviteForm)
      setInviteCode(inv.code)
    } catch (err: any) { setError(err.message) }
  }

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; member: Member } | null>(null)

  async function designateMember(memberId: number, field: 'securite_sante' | 'egalite') {
    setError(null)
    try {
      const res = await fetch(`/api/organization/members/${memberId}/designate`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ field, value: true }),
      })
      if (!res.ok) throw new Error((await res.json()).detail || 'Erreur')
      setShowDesignate(null)
      await loadMembers()
    } catch (err: any) { setError(err.message) }
  }

  function MemberCell({ member, status, role }: { member?: Member; status: string; role?: string }) {
    if (member) {
      return (
        <div onContextMenu={canInvite ? (e) => { e.preventDefault(); setContextMenu({ x: e.clientX, y: e.clientY, member }) } : undefined}
          style={{ background: '#ebf8ff', border: '2px solid #2b6cb0', borderRadius: 8, padding: '8px 10px', textAlign: 'center', minWidth: 110, position: 'relative', cursor: canInvite ? 'context-menu' : 'default' }}>
          <div style={{ fontWeight: 600, fontSize: '.85rem' }}>{member.first_name} {member.last_name}</div>
          <div style={{ fontSize: '.7rem', color: '#4a5568' }}>
            {roleLabel(member.delegue_role)}
            {member.is_delegue_securite_sante && ' 🛡️'}
            {member.is_delegue_egalite && ' ⚖️'}
          </div>
        </div>
      )
    }
    if (canInvite && status !== 'employe') {
      return (
        <button onClick={() => openInvite(status, role || 'membre')}
          style={{ background: '#fff', border: '2px dashed #cbd5e0', borderRadius: 8, padding: '8px 10px', cursor: 'pointer', minWidth: 110, textAlign: 'center', color: '#a0aec0', fontSize: '.85rem' }}>
          + Inviter
        </button>
      )
    }
    return <div style={{ background: '#f7fafc', border: '2px dashed #e2e8f0', borderRadius: 8, padding: '8px 10px', minWidth: 110, textAlign: 'center', color: '#cbd5e0', fontSize: '.8rem' }}>—</div>
  }

  function DesignationCell({ field, label }: { field: 'securite_sante' | 'egalite'; label: string }) {
    const member = members.find(m => field === 'securite_sante' ? m.is_delegue_securite_sante : m.is_delegue_egalite)
    if (member) {
      return (
        <div onClick={() => canInvite && setShowDesignate(field)}
          style={{ background: field === 'securite_sante' ? '#ebf8ff' : '#faf5ff', border: `2px solid ${field === 'securite_sante' ? '#3182ce' : '#805ad5'}`, borderRadius: 8, padding: '8px 10px', textAlign: 'center', minWidth: 110, cursor: canInvite ? 'pointer' : 'default', position: 'relative' }}>
          <div style={{ fontWeight: 600, fontSize: '.85rem' }}>{member.first_name} {member.last_name}</div>
          <div style={{ fontSize: '.7rem', color: '#4a5568' }}>{roleLabel(member.delegue_role)} {label}</div>
        </div>
      )
    }
    if (!canInvite) return <div style={{ background: '#f7fafc', border: '2px dashed #e2e8f0', borderRadius: 8, padding: '8px 10px', minWidth: 110, textAlign: 'center', color: '#cbd5e0', fontSize: '.8rem' }}>—</div>

    return (
      <div style={{ textAlign: 'center' }}>
        <button onClick={() => setShowDesignate(field)}
          style={{ background: '#fff', border: '2px dashed #cbd5e0', borderRadius: 8, padding: '8px 10px', cursor: 'pointer', minWidth: 110, textAlign: 'center', color: '#a0aec0', fontSize: '.85rem' }}>
          + Cliquer pour désigner
        </button>
      </div>
    )
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

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Titulaires restants ({Math.max(0, n - 3)})</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
            {Array.from({ length: Math.max(0, n - 3) }, (_, i) => {
              const filled = members.filter(m => m.delegue_status === 'titulaire' && !['president', 'vice_president', 'secretaire'].includes(m.delegue_role))
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

          <h3 style={{ fontSize: '.9rem', color: 'var(--blue)', marginBottom: 8 }}>Désignations spéciales (Art. L.414-2/3)</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>🛡️ Sécurité/Santé</div>
              <DesignationCell field="securite_sante" label="🛡️" />
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '.7rem', color: '#a0aec0', marginBottom: 4 }}>⚖️ Égalité</div>
              <DesignationCell field="egalite" label="⚖️" />
            </div>
          </div>
        </div>

        {/* Modal : désigner un membre existant */}
        {showDesignate && (
          <div className="card mb-24" style={{ background: '#fffbeb', border: '2px solid #d69e2e' }}>
            {error && <div className="error-msg" style={{ marginBottom: 12 }}>{error}</div>}
            <h3>Désigner {showDesignate === 'securite_sante' ? '🛡️ Sécurité/Santé' : '⚖️ Égalité'}</h3>
            <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>Choisir un membre existant :</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
              {members.filter(m => showDesignate === 'egalite' ? m.delegue_status !== 'employe' : true).map(m => (
                <button key={m.id} onClick={() => designateMember(m.id, showDesignate)}
                  style={{ background: '#ebf8ff', border: '1px solid #2b6cb0', borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: '.85rem' }}>
                  {m.full_name} ({statusLabel(m.delegue_status)})
                </button>
              ))}
            </div>
            <div style={{ borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
              <p style={{ color: 'var(--gray-600)', marginBottom: 8 }}>Ou inviter quelqu'un :</p>
              <button onClick={() => { setShowDesignate(null); openInvite(showDesignate === 'egalite' ? 'titulaire' : 'employe', 'membre', showDesignate === 'securite_sante', showDesignate === 'egalite') }}
                style={{ background: 'var(--blue)', color: '#fff', border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }}>
                + Inviter {showDesignate === 'securite_sante' ? '🛡️ Sécurité/Santé' : '⚖️ Égalité'}
              </button>
              <button onClick={() => setShowDesignate(null)}
                style={{ background: 'var(--gray-300)', color: '#4a5568', border: 'none', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', marginLeft: 8 }}>
                Annuler
              </button>
            </div>
          </div>
        )}

        {/* Modal : invitation classique */}
        {showInvite && (
          <div className="card mb-24">
            <h2>✉️ Inviter</h2>
            {error && <div className="error-msg">{error}</div>}
            <form onSubmit={sendInvite}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <div className="form-group"><label>Prénom *</label><input value={inviteForm.first_name} onChange={e => setInviteForm(p => ({ ...p, first_name: e.target.value }))} required /></div>
                <div className="form-group"><label>Nom *</label><input value={inviteForm.last_name} onChange={e => setInviteForm(p => ({ ...p, last_name: e.target.value }))} required /></div>
              </div>
              <div className="form-group"><label>Email *</label><input type="email" value={inviteForm.email} onChange={e => setInviteForm(p => ({ ...p, email: e.target.value }))} required /></div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="submit" className="btn btn-primary">Générer le code</button>
                <button type="button" onClick={() => setShowInvite(false)} className="btn" style={{ background: 'var(--gray-300)' }}>Annuler</button>
              </div>
            </form>
            {inviteCode && <div className="success-msg mt-16">Code : <span className="invite-code">{inviteCode}</span></div>}
          </div>
        )}
      </div>

      {/* Menu contextuel droit */}
      {contextMenu && (
        <>
          <div onClick={() => setContextMenu(null)}
            style={{ position: 'fixed', inset: 0, zIndex: 999 }} />
          <div style={{
            position: 'fixed', left: contextMenu.x, top: contextMenu.y, zIndex: 1000,
            background: '#fff', border: '1px solid var(--gray-300)', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,.15)',
            padding: '4px 0', minWidth: 200
          }}>
            <div style={{ padding: '6px 12px', fontWeight: 600, fontSize: '.8rem', borderBottom: '1px solid var(--gray-200)' }}>
              {contextMenu.member.full_name}
            </div>
            <button onClick={() => { designateMember(contextMenu.member.id, 'securite_sante'); setContextMenu(null) }}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '.85rem' }}>
              🛡️ Délégué sécurité/santé
            </button>
            {contextMenu.member.delegue_status !== 'employe' && (
              <button onClick={() => { designateMember(contextMenu.member.id, 'egalite'); setContextMenu(null) }}
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '.85rem' }}>
                ⚖️ Délégué à l'égalité
              </button>
            )}
            <button onClick={() => setContextMenu(null)}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', border: 'none', background: 'var(--gray-50)', cursor: 'pointer', fontSize: '.85rem', color: 'var(--gray-600)' }}>
              Annuler
            </button>
          </div>
        </>
      )}
    </>
  )
}
