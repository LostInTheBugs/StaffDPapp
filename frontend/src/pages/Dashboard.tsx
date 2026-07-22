import { useEffect } from 'react'
import { useAuth } from '../hooks/useAuth'
import NavBar from '../components/NavBar'
import { useT } from '../i18n/I18nContext'

export default function Dashboard() {
  const { t } = useT()
  const { user, organization, fetchDashboard } = useAuth()

  useEffect(() => { if (!user) fetchDashboard() }, [])

  if (!user || !organization) return <div className="dashboard"><div className="spinner" /></div>

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
      </div>
    </>
  )
}
