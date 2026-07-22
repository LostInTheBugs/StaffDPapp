import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="container">
      <div className="logo-area">
        <div className="logo-icon">🏢</div>
        <h1>Staff Delegation</h1>
        <p className="subtitle">
          Outil de gestion pour les délégations du personnel au Luxembourg
        </p>
      </div>

      <div className="card">
        <div className="btn-group">
          <Link to="/login" className="btn btn-primary">
            🔑 J'ai déjà un accès
          </Link>
          <Link to="/join" className="btn btn-secondary">
            ✉️ Créer un accès (code d'invitation)
          </Link>
          <Link to="/create" className="btn btn-gold">
            🏛️ Créer une délégation du personnel
          </Link>
        </div>
      </div>

      <p className="text-center mt-16" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
        Conçu pour les entreprises et institutions au Luxembourg 🇱🇺
      </p>
    </div>
  )
}
