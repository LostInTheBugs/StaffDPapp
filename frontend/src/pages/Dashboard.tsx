import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import * as api from '../api/client'

export default function Dashboard() {
  const { user, organization, logout, fetchDashboard } = useAuth()
  const [inviteCode, setInviteCode] = useState<string | null>(null)
  const [invitations, setInvitations] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!user) {
      fetchDashboard()
    }
    loadInvitations()
  }, [])

  async function loadInvitations() {
    try {
      const list = await api.listInvitations()
      setInvitations(list.map(i => i.code))
    } catch {
      // user might not be admin — ignore
    }
  }

  async function generateInvite() {
    setError(null)
    try {
      const inv = await api.createInvitation()
      setInviteCode(inv.code)
      setInvitations(prev => [inv.code, ...prev])
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (!user || !organization) {
    return (
      <div className="dashboard">
        <div className="spinner" />
      </div>
    )
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
            Rôle : <strong>{isAdmin ? 'Administrateur' : 'Membre'}</strong>
          </p>
          {organization.company_name && (
            <p style={{ color: 'var(--gray-600)' }}>Entreprise : {organization.company_name}</p>
          )}
        </div>

        {isAdmin && (
          <div className="card mb-24">
            <h2>✉️ Invitations</h2>
            <p className="subtitle">
              Générez un code pour inviter un nouveau membre à rejoindre la délégation.
            </p>

            {error && <div className="error-msg">{error}</div>}

            <button className="btn btn-secondary mb-16" onClick={generateInvite}>
              + Générer un code d'invitation
            </button>

            {inviteCode && (
              <div className="success-msg mb-16">
                Code généré — à communiquer au membre :
                <div className="invite-code mt-16">{inviteCode}</div>
              </div>
            )}

            {invitations.length > 0 && (
              <>
                <h3 style={{ fontSize: '.95rem', marginBottom: 8 }}>Codes actifs :</h3>
                <ul style={{ listStyle: 'none', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {invitations.map(code => (
                    <li key={code} className="invite-code" style={{ fontSize: '1rem', padding: '6px 14px' }}>
                      {code}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}

        <div className="card">
          <h2>📋 Informations</h2>
          <p style={{ color: 'var(--gray-600)' }}>
            <strong>Délégation :</strong> {organization.name}<br />
            <strong>Pays :</strong> Luxembourg 🇱🇺<br />
            <strong>Identifiant :</strong> {organization.slug}
          </p>
        </div>
      </div>
    </>
  )
}
