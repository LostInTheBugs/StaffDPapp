import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'
import NavBar from '../components/NavBar'
import { useT } from '../i18n/I18nContext'

export default function Dashboard() {
  const { t } = useT()
  const { user, organization, fetchDashboard } = useAuth()
  const [inviteForm, setInviteForm] = useState({
    email: '', first_name: '', last_name: '',
    delegue_status: 'titulaire' as string,
    delegue_role: 'membre' as string,
    is_delegue_securite_sante: false,
    is_delegue_egalite: false,
  })
  const [inviteCode, setInviteCode] = useState<string | null>(null)
  const [invitations, setInvitations] = useState<api.InvitationResponse[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (!user) fetchDashboard(); loadInvitations() }, [])

  async function loadInvitations() {
    try { setInvitations(await api.listInvitations()) } catch { /* */ }
  }

  function update(field: string, value: string | boolean) {
    setInviteForm(prev => {
      const next = { ...prev, [field]: value }
      // Si statut = employé → forcer sécurité/santé + fonction = membre
      if (field === 'delegue_status' && value === 'employe') {
        next.is_delegue_securite_sante = true
        next.delegue_role = 'membre'
      }
      return next
    })
  }

  async function generateInvite(e: React.FormEvent) {
    e.preventDefault(); setError(null)
    try {
      const inv = await api.createInvitation(inviteForm)
      setInviteCode(inv.code)
      setInvitations(prev => [inv, ...prev])
      setInviteForm({
        email: '', first_name: '', last_name: '',
        delegue_status: 'titulaire', delegue_role: 'membre',
        is_delegue_securite_sante: false, is_delegue_egalite: false,
      })
    } catch (err: any) { setError(err.message) }
  }

  const statusLabel = (s: string) => api.DELEGUE_STATUS.find(r => r.value === s)?.label || s
  const roleLabel = (r: string) => api.DELEGUE_ROLES.find(x => x.value === r)?.label || r

  if (!user || !organization) return <div className="dashboard"><div className="spinner" /></div>
  const isAdmin = user.role === 'admin'

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <div className="card mb-24">
          <h2>{t('dashboard.org')}</h2>
          <p><strong>{organization.name}</strong></p>
          {organization.company_name && <p style={{ color: 'var(--gray-600)' }}>{organization.company_name}</p>}
          <p style={{ color: 'var(--gray-600)' }}>{t('dashboard.employees')} : <strong>{organization.employee_count}</strong> salariés</p>
          <p style={{ color: 'var(--gray-600)' }}>
            {t('dashboard.delegates')} : <strong>{organization.required_titulaires} titulaires</strong> + {organization.required_titulaires} suppléants
          </p>
          <p style={{ color: 'var(--gray-600)', fontSize: '.8rem' }}>Art. L.412-1 — Luxembourg 🇱🇺</p>
        </div>

        {isAdmin && (
          <div className="card mb-24">
            <h2>{t('dashboard.invite')}</h2>
            {error && <div className="error-msg">{error}</div>}
            <form onSubmit={generateInvite}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <div className="form-group"><label>Prénom *</label><input value={inviteForm.first_name} onChange={e => update('first_name', e.target.value)} required /></div>
                <div className="form-group"><label>Nom *</label><input value={inviteForm.last_name} onChange={e => update('last_name', e.target.value)} required /></div>
              </div>
              <div className="form-group"><label>Email *</label><input type="email" value={inviteForm.email} onChange={e => update('email', e.target.value)} required /></div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <div className="form-group">
                  <label>Statut *</label>
                  <select value={inviteForm.delegue_status} onChange={e => update('delegue_status', e.target.value)}
                    style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem' }}>
                    {api.DELEGUE_STATUS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Fonction {inviteForm.delegue_status === 'employe' && '(non applicable)'}</label>
                  <select value={inviteForm.delegue_role} onChange={e => update('delegue_role', e.target.value)}
                    disabled={inviteForm.delegue_status === 'employe'}
                    style={{ width:'100%', padding:'11px 14px', border:'1.5px solid var(--gray-300)', borderRadius:'var(--radius)', fontSize:'1rem', opacity: inviteForm.delegue_status === 'employe' ? 0.5 : 1 }}>
                    {api.DELEGUE_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </div>
              </div>

              <div style={{ background:'var(--gray-50)', borderRadius:'var(--radius)', padding:'14px 16px', marginBottom:16 }}>
                <p style={{ fontWeight:700, fontSize:'.88rem', marginBottom:10 }}>Désignations (Art. L.414-2/3)</p>
                <label style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8, cursor: inviteForm.delegue_status === 'employe' ? 'default' : 'pointer' }}>
                  <input type="checkbox" checked={inviteForm.is_delegue_securite_sante} onChange={e => update('is_delegue_securite_sante', e.target.checked)}
                    disabled={inviteForm.delegue_status === 'employe'} />
                  🛡️ Délégué à la sécurité et à la santé <small style={{ color:'var(--gray-600)' }}>(obligatoire si non-élu)</small>
                </label>
                <label style={{ display:'flex', alignItems:'center', gap:8, cursor: inviteForm.delegue_status === 'employe' ? 'default' : 'pointer' }}>
                  <input type="checkbox" checked={inviteForm.is_delegue_egalite} onChange={e => update('is_delegue_egalite', e.target.checked)}
                    disabled={inviteForm.delegue_status === 'employe'} />
                  ⚖️ Délégué à l'égalité <small style={{ color:'var(--gray-600)' }}>(doit être titulaire ou suppléant)</small>
                </label>
              </div>

              <button type="submit" className="btn btn-secondary mb-16">+ Générer un code</button>
            </form>

            {inviteCode && <div className="success-msg mb-16">Code :<div className="invite-code mt-16">{inviteCode}</div></div>}

            {invitations.length > 0 && (
              <>
                <h3 style={{ fontSize:'.95rem', marginBottom:8 }}>Invitations actives :</h3>
                <table style={{ width:'100%', borderCollapse:'collapse', fontSize:'.85rem' }}>
                  <thead><tr style={{ borderBottom:'2px solid var(--gray-300)' }}>
                    <th style={{ padding:'6px 8px', textAlign:'left' }}>Code</th>
                    <th style={{ padding:'6px 8px', textAlign:'left' }}>Membre</th>
                    <th style={{ padding:'6px 8px', textAlign:'left' }}>Email</th>
                    <th style={{ padding:'6px 8px', textAlign:'left' }}>Statut / Fonction</th>
                  </tr></thead>
                  <tbody>
                    {invitations.map(inv => (
                      <tr key={inv.code} style={{ borderBottom:'1px solid var(--gray-300)' }}>
                        <td style={{ padding:'6px 8px', fontFamily:'monospace' }}>{inv.code}</td>
                        <td style={{ padding:'6px 8px' }}>{inv.first_name} {inv.last_name}</td>
                        <td style={{ padding:'6px 8px' }}>{inv.email}</td>
                        <td style={{ padding:'6px 8px' }}>
                          {statusLabel(inv.delegue_status)} / {roleLabel(inv.delegue_role)}
                          {inv.is_delegue_securite_sante && <span style={{ background:'#ebf8ff', color:'#2b6cb0', padding:'1px 6px', borderRadius:4, fontSize:'.7rem', fontWeight:700, marginLeft:4 }}>🛡️</span>}
                          {inv.is_delegue_egalite && <span style={{ background:'#faf5ff', color:'#6b46c1', padding:'1px 6px', borderRadius:4, fontSize:'.7rem', fontWeight:700, marginLeft:4 }}>⚖️</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}
      </div>
    </>
  )
}
