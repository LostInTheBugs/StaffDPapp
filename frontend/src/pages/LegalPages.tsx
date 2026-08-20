import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import * as api from '../api/client'

const STATUS_BADGE: Record<string, React.CSSProperties> = {
  protected: { background: '#e6f4ea', color: 'var(--green)', padding: '2px 8px', borderRadius: 10, fontSize: '.75rem' },
  expired: { background: '#fdecea', color: 'var(--red)', padding: '2px 8px', borderRadius: 10, fontSize: '.75rem' },
  unknown: { background: 'var(--gray-200)', color: 'var(--gray-600)', padding: '2px 8px', borderRadius: 10, fontSize: '.75rem' },
}

export function FormationPage() {
  const { user } = useAuth()
  const { t } = useT()
  const [data, setData] = useState<api.FormationOverview | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const isBureau = user?.role === 'admin' || ['president', 'vice_president', 'secretaire'].includes(user?.delegue_role || '')

  async function load() {
    try { setData(await api.getFormationOverview()) } catch (e: any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  async function togglePrimo(userId: number, current: boolean) {
    try {
      await api.setFirstMandate(userId, !current)
      await load()
    } catch (e: any) { setErr(e.message) }
  }

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>🎓 {t('formation.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('formation.subtitle')} — <em>Art. L.415-9</em>
        </p>
        {err && <div className="error-msg">{err}</div>}
        {!data && <div className="spinner" />}
        {data && (
          <>
            <p style={{ fontSize: '.8rem', color: 'var(--gray-600)' }}>{t('formation.year_label')} : {data.year} · {t('formation.entitlement_rules')}</p>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', marginTop: 8 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                  <th style={{ padding: 6, textAlign: 'left' }}>{t('formation.member')}</th>
                  <th style={{ padding: 6, textAlign: 'left' }}>{t('formation.status')}</th>
                  <th style={{ padding: 6, textAlign: 'right' }}>{t('formation.entitlement')}</th>
                  <th style={{ padding: 6, textAlign: 'right' }}>{t('formation.used')}</th>
                  <th style={{ padding: 6, textAlign: 'right' }}>{t('formation.remaining')}</th>
                  {isBureau && <th style={{ padding: 6, textAlign: 'center' }}>Primo-élu (+16 h)</th>}
                </tr>
              </thead>
              <tbody>
                {data.members.map(m => (
                  <tr key={m.user_id} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                    <td style={{ padding: 6 }}>{m.full_name}</td>
                    <td style={{ padding: 6 }}>{t(`status.${m.delegue_status}`)}</td>
                    <td style={{ padding: 6, textAlign: 'right' }}>{m.entitlement_hours} h</td>
                    <td style={{ padding: 6, textAlign: 'right' }}>{m.used_hours} h</td>
                    <td style={{ padding: 6, textAlign: 'right', fontWeight: 600, color: m.remaining_hours > 0 ? 'var(--green)' : 'var(--red)' }}>{m.remaining_hours} h</td>
                    {isBureau && (
                      <td style={{ padding: 6, textAlign: 'center' }}>
                        <input type="checkbox" checked={m.is_first_mandate} onChange={() => togglePrimo(m.user_id, m.is_first_mandate)} />
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </>
  )
}

export function SafetyRegisterPage() {
  const { user } = useAuth()
  const { t } = useT()
  const [entries, setEntries] = useState<api.SafetyRegisterEntry[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [form, setForm] = useState({ entry_date: '', location: '', description: '' })
  const canWrite = user?.role === 'admin' || ['president', 'vice_president', 'secretaire'].includes(user?.delegue_role || '') || !!user?.is_delegue_securite_sante

  async function load() {
    try { setEntries(await api.listSafetyRegister()) } catch (e: any) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  async function create(e: FormEvent) {
    e.preventDefault(); setErr(null)
    try {
      await api.createSafetyRegisterEntry({ entry_date: form.entry_date, location: form.location, description: form.description })
      setForm({ entry_date: '', location: '', description: '' })
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function countersign(id: number) {
    const name = prompt(t('register.chef_prompt'))
    if (!name) return
    try {
      await api.countersignEntry(id, name)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function remove(id: number) {
    if (!confirm(t('register.delete_confirm'))) return
    try {
      await api.deleteSafetyRegisterEntry(id)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>🛡️ {t('register.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('register.subtitle')} — <em>Art. L.414-14</em>
        </p>
        {err && <div className="error-msg">{err}</div>}

        {canWrite && (
          <form onSubmit={create} className="card mb-24" style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <label style={{ fontSize: '.8rem' }}>{t('register.date')} <input required type="date" value={form.entry_date} onChange={e => setForm({ ...form, entry_date: e.target.value })} /></label>
              <input placeholder={t('register.location_ph')} value={form.location} maxLength={200} onChange={e => setForm({ ...form, location: e.target.value })} />
            </div>
            <textarea required placeholder={t('register.description_ph')} rows={3} maxLength={5000} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} />
            <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start' }}>+ {t('register.add')}</button>
          </form>
        )}

        {entries.length === 0 && <p style={{ color: 'var(--gray-600)' }}>{t('register.empty')}</p>}
        {entries.map(e => (
          <div key={e.id} className="card mb-24" style={{ padding: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
              <div style={{ fontSize: '.85rem' }}>
                <strong>📅 {new Date(e.entry_date).toLocaleDateString()}</strong>
                {e.location && <span> · 📍 {e.location}</span>}
                <span style={{ marginLeft: 8, fontSize: '.75rem', color: 'var(--gray-600)' }}>{e.delegate_name} · {t('register.by')} {e.created_by_name}</span>
              </div>
              <span style={e.status === 'countersigned' ? STATUS_BADGE.protected : { ...STATUS_BADGE.expired, color: '#b06000', background: '#fff4e5' }}>
                {e.status === 'countersigned' ? '✅ ' + t('register.countersigned') : '⏳ ' + t('register.pending')}
              </span>
            </div>
            <p style={{ fontSize: '.85rem', margin: '6px 0' }}>{e.description}</p>
            {e.status === 'countersigned' && e.chef_service_name && (
              <p style={{ fontSize: '.78rem', color: 'var(--gray-600)', margin: 0 }}>
                ✍️ {t('register.chef_label')} : <strong>{e.chef_service_name}</strong> — {e.countersigned_at ? new Date(e.countersigned_at).toLocaleDateString() : ''}
              </p>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              {e.can_countersign && e.status === 'pending' && (
                <button className="btn" style={{ fontSize: '.75rem', padding: '4px 10px', background: 'var(--blue)', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }} onClick={() => countersign(e.id)}>✍️ {t('register.countersign')}</button>
              )}
              {e.can_delete && (
                <button className="btn" style={{ fontSize: '.75rem', padding: '4px 10px', background: 'var(--gray-300)', border: 'none', borderRadius: 4, cursor: 'pointer', color: 'var(--red)' }} onClick={() => remove(e.id)}>🗑️</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export function ProtectionPage() {
  const { t } = useT()
  const [data, setData] = useState<{ today: string; people: api.ProtectionPerson[] } | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    api.getProtection().then(setData).catch((e: any) => setErr(e.message))
  }, [])

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>🛡️ {t('protection.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('protection.subtitle')} — <em>Art. L.415-10</em>
        </p>
        {err && <div className="error-msg">{err}</div>}
        {!data && <div className="spinner" />}
        {data && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem', marginTop: 8 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                <th style={{ padding: 6, textAlign: 'left' }}>{t('protection.name')}</th>
                <th style={{ padding: 6, textAlign: 'left' }}>{t('protection.role')}</th>
                <th style={{ padding: 6, textAlign: 'left' }}>{t('protection.until')}</th>
                <th style={{ padding: 6, textAlign: 'right' }}>{t('protection.days_left')}</th>
                <th style={{ padding: 6, textAlign: 'center' }}>{t('protection.status')}</th>
              </tr>
            </thead>
            <tbody>
              {data.people.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                  <td style={{ padding: 6 }}>
                    {p.name}
                    {p.kind === 'candidate' && <span style={{ fontSize: '.72rem', color: 'var(--gray-600)' }}> · {p.election}</span>}
                  </td>
                  <td style={{ padding: 6 }}>{t(`protection.role_${p.kind}`)}</td>
                  <td style={{ padding: 6 }}>{p.protected_until ? new Date(p.protected_until).toLocaleDateString() : '—'}</td>
                  <td style={{ padding: 6, textAlign: 'right' }}>
                    {p.days_left !== null && (p.days_left >= 0 ? `${p.days_left} ${t('protection.days')}` : '—')}
                  </td>
                  <td style={{ padding: 6, textAlign: 'center' }}>
                    <span style={STATUS_BADGE[p.status]}>{t(`protection.status_${p.status}`)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
