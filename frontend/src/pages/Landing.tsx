import { Link } from 'react-router-dom'
import { useT, LANGS } from '../i18n/I18nContext'
import Footer from '../components/Footer'

export default function Landing() {
  const { t, lang, setLang } = useT()
  return (
    <div className="container">
      <div className="logo-area">
        <div className="logo-icon">🏢</div>
        <h1>{t('landing.title')}</h1>
        <p className="subtitle">{t('landing.subtitle')}</p>
        {/* Sélecteur de langue — langue choisie ici appliquée au compte après login */}
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
          {LANGS.map(l => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              style={{
                background: lang === l.code ? 'var(--blue)' : '#fff',
                color: lang === l.code ? '#fff' : 'var(--gray-600)',
                border: lang === l.code ? '1px solid var(--blue)' : '1px solid var(--gray-300)',
                borderRadius: 999, padding: '4px 12px', cursor: 'pointer', fontSize: '.8rem', fontWeight: 600,
              }}
            >
              {l.label}
            </button>
          ))}
        </div>
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
      <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '8px', padding: '12px 16px', fontSize: '.78rem', color: '#856404', textAlign: 'center', maxWidth: '600px', margin: '24px auto 0' }}>
        ⚠️ <strong>Application expérimentale</strong> — Cet outil est fourni à titre de démonstration uniquement. Il ne constitue en aucun cas un conseil juridique et n'est pas garanti conforme à la législation luxembourgeoise. L'utilisation de cette application se fait aux risques et périls de l'utilisateur. Pour toute question relative au droit du travail luxembourgeois, consultez un professionnel qualifié ou la Chambre des Salariés (CSL).
      </div>
      <Footer />
    </div>
  )
}
