import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import Footer from '../components/Footer'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'

interface ArchiveEntry {
  id: number
  meeting_id: number
  meeting_title: string | null
  meeting_date: string | null
  status: string
  is_encrypted: boolean
  created_by_name: string | null
  validated_by_name: string | null
  validated_at: string | null
  created_at: string | null
}

export default function MinutesArchive() {
  const { t } = useT()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [rows, setRows] = useState<ArchiveEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('tous')

  useEffect(() => {
    if (!token) return
    fetch('/api/minutes', { headers: { Authorization: `Bearer ${token}` } })
      .then(r => { if (!r.ok) throw new Error('Archive indisponible'); return r.json() })
      .then(setRows)
      .catch(e => setErr(e.message))
      .finally(() => setLoading(false))
  }, [token])

  const filtered = rows.filter(r => {
    if (statusFilter !== 'tous' && r.status !== statusFilter) return false
    if (!query) return true
    const q = query.toLowerCase()
    return (r.meeting_title ?? '').toLowerCase().includes(q)
  })

  return (
    <>
      <NavBar />
      <div className="container">
        <h2>📚 {t('archive.title')}</h2>
        <p style={{ color: 'var(--gray-600)', marginBottom: 16 }}>{t('archive.subtitle')}</p>

        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          <input
            type="search"
            placeholder={t('archive.search')}
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 12px', border: '1.5px solid var(--gray-300)', borderRadius: 'var(--radius)' }}
          />
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            style={{ padding: '8px 12px', border: '1.5px solid var(--gray-300)', borderRadius: 'var(--radius)' }}
          >
            <option value="tous">{t('archive.all')}</option>
            <option value="brouillon">{t('archive.draft')}</option>
            <option value="valide">{t('archive.validated')}</option>
          </select>
        </div>

        {err && <div className="error-msg">{err}</div>}

        {loading ? (
          <div className="spinner" />
        ) : filtered.length === 0 ? (
          <p style={{ color: 'var(--gray-600)', textAlign: 'center', padding: 30 }}>{t('archive.empty')}</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                <th style={{ padding: '8px', textAlign: 'left' }}>{t('archive.date')}</th>
                <th style={{ padding: '8px', textAlign: 'left' }}>{t('archive.meeting')}</th>
                <th style={{ padding: '8px', textAlign: 'left' }}>{t('archive.status')}</th>
                <th style={{ padding: '8px', textAlign: 'left' }}>{t('archive.written_by')}</th>
                <th style={{ padding: '8px', textAlign: 'left' }}>{t('archive.validated_by')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr
                  key={r.id}
                  onClick={() => navigate(`/meetings/${r.meeting_id}/minutes`)}
                  style={{ borderBottom: '1px solid var(--gray-300)', cursor: 'pointer' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#f5f7fa')}
                  onMouseLeave={e => (e.currentTarget.style.background = '')}
                >
                  <td style={{ padding: '8px' }}>
                    {r.meeting_date ? new Date(r.meeting_date).toLocaleDateString('fr-LU') : '—'}
                  </td>
                  <td style={{ padding: '8px', fontWeight: 500 }}>
                    {r.meeting_title ?? `PV #${r.id}`} {r.is_encrypted && '🔒'}
                  </td>
                  <td style={{ padding: '8px' }}>
                    <span
                      style={{
                        background: r.status === 'valide' ? '#dcfce7' : '#f3f4f6',
                        color: r.status === 'valide' ? '#166534' : '#4b5563',
                        borderRadius: 999,
                        padding: '2px 10px',
                        fontSize: '.75rem',
                        fontWeight: 600,
                      }}
                    >
                      {r.status === 'valide' ? t('archive.validated') : t('archive.draft')}
                    </span>
                  </td>
                  <td style={{ padding: '8px', color: 'var(--gray-600)' }}>{r.created_by_name ?? '—'}</td>
                  <td style={{ padding: '8px', color: 'var(--gray-600)' }}>
                    {r.validated_by_name
                      ? `${r.validated_by_name}${r.validated_at ? ` · ${new Date(r.validated_at).toLocaleDateString('fr-LU')}` : ''}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Footer />
    </>
  )
}
