import { Link } from 'react-router-dom'
import NavBar from '../components/NavBar'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import { useEffect, useState } from 'react'

interface Member {
  id: number; full_name: string; email?: string; role: string; delegue_status: string; delegue_role: string
}

export default function ContactPage() {
  const { organization, token, user } = useAuth()
  const { t } = useT()
  const [bureau, setBureau] = useState<Member[]>([])

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/organization/members', { headers: { Authorization: 'Bearer ' + token } })
        const data = await res.json()
        // Bureau = admin + président/vice-président/secrétaire (rôles légaux)
        const members: Member[] = data || []
        const b = members.filter(m =>
          m.role === 'admin' || ['president', 'vice_president', 'secretaire'].includes(m.delegue_role)
        )
        setBureau(b)
      } catch { /* */ }
    }
    if (token) load()
  }, [token])

  const hasContact = organization?.contact_email || organization?.contact_phone || organization?.contact_hours

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ marginBottom: 16 }}>📇 {t('contact.title')}</h1>

        {!hasContact && (
          <div className="card mb-24" style={{ borderLeft: '4px solid var(--gray-400)' }}>
            <p style={{ color: 'var(--gray-600)' }}>{t('contact.empty')}</p>
            {user?.role === 'admin' && (
              <p style={{ marginTop: 8 }}>
                <Link to="/organization" style={{ color: 'var(--blue)' }}>{t('contact.admin_hint')}</Link>
              </p>
            )}
          </div>
        )}

        {hasContact && (
          <div className="card mb-24">
            <h2>{t('contact.coordinates')}</h2>
            <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
              {organization?.contact_email && (
                <p>✉️ <a href={`mailto:${organization.contact_email}`} style={{ color: 'var(--blue)' }}>{organization.contact_email}</a></p>
              )}
              {organization?.contact_phone && (
                <p>📞 <a href={`tel:${organization.contact_phone.replace(/[^+\d]/g, '')}`} style={{ color: 'var(--blue)' }}>{organization.contact_phone}</a></p>
              )}
              {organization?.contact_hours && (
                <p style={{ whiteSpace: 'pre-line' }}>🕐 {organization.contact_hours}</p>
              )}
            </div>
          </div>
        )}

        <div className="card">
          <h2>{t('contact.bureau')}</h2>
          <p style={{ color: 'var(--gray-600)', marginTop: 4 }}>
            {t('contact.bureau_hint')}
          </p>
          {bureau.length === 0 ? (
            <p style={{ marginTop: 12, color: 'var(--gray-500)' }}>{t('contact.no_bureau')}</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 12, fontSize: '.9rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--gray-300)', textAlign: 'left' }}>
                  <th style={{ padding: '8px' }}>{t('contact.name')}</th>
                  <th style={{ padding: '8px' }}>{t('contact.function')}</th>
                </tr>
              </thead>
              <tbody>
                {bureau.map(m => (
                  <tr key={m.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                    <td style={{ padding: '8px' }}>{m.full_name}</td>
                    <td style={{ padding: '8px' }}>
                      {m.role === 'admin' ? t('contact.admin') : t(`contact.role_${m.delegue_role}`)}
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
