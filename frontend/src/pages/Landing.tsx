import { Link } from 'react-router-dom'
import { useT } from '../i18n/I18nContext'

export default function Landing() {
  const { t } = useT()
  return (
    <div className="container">
      <div className="logo-area">
        <div className="logo-icon">🏢</div>
        <h1>{t('landing.title')}</h1>
        <p className="subtitle">{t('landing.subtitle')}</p>
      </div>
      <div className="card">
        <div className="btn-group">
          <Link to="/login" className="btn btn-primary">{t('landing.login')}</Link>
          <Link to="/join" className="btn btn-secondary">{t('landing.join')}</Link>
          <Link to="/create" className="btn btn-gold">{t('landing.create')}</Link>
        </div>
      </div>
      <p className="text-center mt-16" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
        {t('landing.footer')}
      </p>
    </div>
  )
}
