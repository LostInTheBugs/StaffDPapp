import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function Dashboard() {
  const { user, organization, logout, fetchDashboard } = useAuth()
  const [inviteForm, setInviteForm] = useState({
    email: '',
    first_name: '',
    last_name: '',
    delegue_role: 'titulaire',
    is_delegue_securite_sante: false,
    is_delegue_egalite: false,
  })
  const [inviteCode, setInviteCode] = useState<string | null>(null)
  const [invitations, setInvitations] = useState<api.InvitationResponse[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) fetchDashboard()
    loadInvitations()
  }, [])

  async function loadInvitations() {
    try {
      const list = await api.listInvitations()
      setInvitations(list)
    } catch { /* not admin */ }
  }

  function updateInvite(field: string, value: string | boolean) {
    setInviteForm(prev => ({ ...prev, [field]: value }))
  }

  async function generateInvite(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const inv = await api.createInvitation(inviteForm)
      setInviteCode(inv.code)
      setInvitations(prev => [inv, ...prev])
      setInviteForm({
        email: '', first_name: '', last_name: '',
        delegue_role: 'titulaire',
        is_delegue_securite_sante: false,
        is_delegue_egalite: false,
      })
    } catch (err: any) {
      setError(err.message)
    }
  }

  const getRoleLabel = (role: string) =>
    api.DELEGUE_ROLES.find(r => r.value === role)?.label || role

  const specialBadges = (inv: { is_delegue_securite_sante?: boolean; is_delegue_egalite?: boolean }) => (
    <>
      {inv.is_delegue_securite_sante && (
        <span style={{
          background: '#ebf8ff', color: '#2b6cb0', padding: '1px 6px',
          borderRadius: 4, fontSize: '.7rem', fontWeight: 700, marginLeft: 4,
        }}>🛡️ Séc/Santé</span>
      )}
      {inv.is_delegue_egalite && (
        <span style={{
          background: '#faf5ff', color: '#6b46c1', padding: '1px 6px',
          borderRadius: 4, fontSize: '.7rem', fontWeight: 700, marginLeft: 4,
        }}>⚖️ Égalité</span>
      )}
    </>
  )

  if (!user || !organization) {
    return <div className="dashboard"><div className="spinner" /></div>
  }

  const isAdmin = user.role === 'admin'

  return (
    <>
      <header className="header">
        <h1>🏢 {organization.name}</h1>
        <button onClick={logout}>Déconnexion</button>
      </header>

      <div className="dashboard">
        <div className="card mb-24">
          <h2>👤 Mon profil</h2>
          <p><strong>{user.full_name}</strong></p>
          <p style={{ color: 'var(--gray-600)' }}>{user.email}</p>
          <p style={{ color: 'var(--gray-600)' }}>
            Rôle : <strong>{isAdmin ? 'Administrateur' : getRoleLabel(user.delegue_role)}</strong>
            {user.is_delegue_securite_sante && ' + 🛡️ Délégué Sécurité/Santé'}
            {user.is_delegue_egalite && ' + ⚖️ Délégué Égalité'}
          </p>
        </div>

        <div className="card mb-24">
          <h2>📊 Informations délégation</h2>
          <p><strong>{organization.name}</strong></p>
          {organization.company_name && (
            <p style={{ color: 'var(--gray-600)' }}>Entreprise : {organization.company_name}</p>
          )}
          <p style={{ color: 'var(--gray-600)' }}>
            Effectif : <strong>{organization.employee_count}</strong> salariés
          </p>
          <p style={{ color: 'var(--gray-600)' }}>
            Délégués requis : <strong>{organization.required_titulaires} titulaires</strong>
            {' '}+ {organization.required_titulaires} suppléants
          </p>
          <p style={{ color: 'var(--gray-600)', fontSize: '.8rem' }}>
            Art. L.412-1 du Code du travail — Luxembourg 🇱🇺
          </p>
        </div>

        {isAdmin && (
          <div className="card mb-24">
            <h2>✉️ Inviter un membre</h2>
            <p className="subtitle">
              Remplissez les informations du délégué. Un code d'invitation sera généré.
            </p>

            {error && <div className="error-msg">{error}</div>}

            <form onSubmit={generateInvite}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                <div className="form-group">
                  <label htmlFor="inv_first_name">Prénom *</label>
                  <input id="inv_first_name" type="text" value={inviteForm.first_name}
                    onChange={e => updateInvite('first_name', e.target.value)} required />
                </div>
                <div className="form-group">
                  <label htmlFor="inv_last_name">Nom *</label>
                  <input id="inv_last_name" type="text" value={inviteForm.last_name}
                    onChange={e => updateInvite('last_name', e.target.value)} required />
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="inv_email">Email *</label>
                <input id="inv_email" type="email" value={inviteForm.email}
                  onChange={e => updateInvite('email', e.target.value)} required />
              </div>
              <div className="form-group">
                <label htmlFor="inv_role">Rôle dans la délégation *</label>
                <select id="inv_role" value={inviteForm.delegue_role}
                  onChange={e => updateInvite('delegue_role', e.target.value)}
                  style={{ width: '100%', padding: '11px 14px', border: '1.5px solid var(--gray-300)', borderRadius: 'var(--radius)', fontSize: '1rem' }}>
                  {api.DELEGUE_ROLES.map(r => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>

              <div style={{
                background: 'var(--gray-50)', borderRadius: 'var(--radius)',
                padding: '14px 16px', marginBottom: 16,
              }}>
                <p style={{ fontWeight: 700, fontSize: '.88rem', marginBottom: 10 }}>
                  Désignations spéciales (Art. L.414-2/3)
                </p>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, cursor: 'pointer' }}>
                  <input type="checkbox"
                    checked={inviteForm.is_delegue_securite_sante}
                    onChange={e => updateInvite('is_delegue_securite_sante', e.target.checked)} />
                  <span>🛡️ Délégué à la sécurité et à la santé</span>
                  <span style={{ fontSize: '.75rem', color: 'var(--gray-600)' }}>
                    (peut être un salarié non-élu)
                  </span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input type="checkbox"
                    checked={inviteForm.is_delegue_egalite}
                    onChange={e => updateInvite('is_delegue_egalite', e.target.checked)} />
                  <span>⚖️ Délégué à l'égalité</span>
                  <span style={{ fontSize: '.75rem', color: 'var(--gray-600)' }}>
                    (doit être membre élu : titulaire ou suppléant)
                  </span>
                </label>
              </div>

              <button type="submit" className="btn btn-secondary mb-16">
                + Générer un code d'invitation
              </button>
            </form>

            {inviteCode && (
              <div className="success-msg mb-16">
                Code — à communiquer au membre :
                <div className="invite-code mt-16">{inviteCode}</div>
              </div>
            )}

            {invitations.length > 0 && (
              <>
                <h3 style={{ fontSize: '.95rem', marginBottom: 8 }}>Invitations actives :</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                      <th style={{ padding: '6px 8px', textAlign: 'left' }}>Code</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left' }}>Membre</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left' }}>Email</th>
                      <th style={{ padding: '6px 8px', textAlign: 'left' }}>Rôle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invitations.map(inv => (
                      <tr key={inv.code} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                        <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{inv.code}</td>
                        <td style={{ padding: '6px 8px' }}>{inv.first_name} {inv.last_name}</td>
                        <td style={{ padding: '6px 8px' }}>{inv.email}</td>
                        <td style={{ padding: '6px 8px' }}>
                          {getRoleLabel(inv.delegue_role)}
                          {specialBadges(inv)}
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
