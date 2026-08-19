import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import * as api from '../api/client'

interface Notice extends api.NoticePost {}

export default function NoticeBoard() {
  const { user } = useAuth()
  const { t } = useT()

  const [notices, setNotices] = useState<Notice[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ title: '', body: '', pinned: false })
  const [editing, setEditing] = useState<Notice | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  // Droits d'écriture (Art. L.414-16) : admin, bureau, délégués désignés
  const canPost = !!user && (
    user.role === 'admin'
    || user.delegue_role === 'president'
    || user.delegue_role === 'vice_president'
    || user.delegue_role === 'secretaire'
    || user.is_delegue_securite_sante
    || user.is_delegue_egalite
  )
  const isBureau = !!user && (user.role === 'admin' || user.delegue_role === 'president' || user.delegue_role === 'vice_president' || user.delegue_role === 'secretaire')

  useEffect(() => { load() }, [])

  async function load() {
    try {
      setNotices(await api.listNotices())
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  function canEdit(n: Notice) {
    return !!user && (n.created_by_id === user.id || isBureau)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setErr(null); setMsg(null)
    try {
      if (editing) {
        await api.updateNotice(editing.id, { title: form.title, body: form.body, pinned: form.pinned })
        setMsg(t('notices.updated'))
      } else {
        await api.createNotice({ title: form.title, body: form.body, pinned: form.pinned })
        setMsg(t('notices.created'))
      }
      setShowForm(false); setEditing(null); setForm({ title: '', body: '', pinned: false })
      await load()
    } catch (e: any) { setErr(e.message) }
  }

  function startEdit(n: Notice) {
    setEditing(n)
    setForm({ title: n.title, body: n.body, pinned: n.pinned })
    setShowForm(true)
  }

  async function remove(n: Notice) {
    if (!confirm(t('notices.delete_confirm'))) return
    setErr(null)
    try {
      await api.deleteNotice(n.id)
      await load()
    } catch (e: any) { setErr(e.message) }
  }

  function fmtDate(iso: string | null) {
    if (!iso) return ''
    return new Date(iso).toLocaleDateString() + ' ' + new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  if (!user) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>📌 {t('notices.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('notices.subtitle')} — <em>Art. L.414-16 (Code du travail)</em>
        </p>

        {err && <div className="error-msg">{err}</div>}
        {msg && <p style={{ color: 'var(--green)' }}>{msg}</p>}

        {canPost && !showForm && (
          <button className="btn btn-primary" onClick={() => { setShowForm(true); setEditing(null); setForm({ title: '', body: '', pinned: false }); setErr(null) }}>
            {t('notices.new')}
          </button>
        )}

        {canPost && showForm && (
          <form onSubmit={submit} className="card mb-24" style={{ marginTop: 12 }}>
            <h3>{editing ? t('notices.edit_title') : t('notices.new_title')}</h3>
            <div className="form-group">
              <label>{t('notices.post_title')}</label>
              <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required maxLength={200} />
            </div>
            <div className="form-group">
              <label>{t('notices.post_body')}</label>
              <textarea value={form.body} onChange={e => setForm({ ...form, body: e.target.value })} required rows={5} style={{ width: '100%' }} />
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 400, fontSize: '.85rem', marginBottom: 10 }}>
              <input type="checkbox" checked={form.pinned} onChange={e => setForm({ ...form, pinned: e.target.checked })} />
              📌 {t('notices.pin')}
            </label>
            <div style={{ display: 'flex', gap: 12 }}>
              <button type="submit" className="btn btn-primary">{t('notices.save')}</button>
              <button type="button" className="btn" style={{ background: 'var(--gray-300)' }} onClick={() => { setShowForm(false); setEditing(null); setErr(null) }}>
                {t('organigramme.cancel')}
              </button>
            </div>
          </form>
        )}

        <div style={{ borderTop: '1px solid var(--gray-200)', margin: '16px 0 12px' }} />

        {loading ? <div className="spinner" /> : notices.length === 0 ? (
          <p style={{ color: 'var(--gray-600)' }}>{t('notices.empty')}</p>
        ) : (
          notices.map(n => (
            <div key={n.id} className="card mb-24" style={{ borderLeft: n.pinned ? '4px solid var(--blue)' : '4px solid var(--gray-200)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <h3 style={{ margin: 0, fontSize: '1.05rem' }}>
                    {n.pinned && <span title={t('notices.pin')}>📌 </span>}
                    {n.title}
                  </h3>
                  <p style={{ margin: '2px 0 8px', fontSize: '.75rem', color: 'var(--gray-600)' }}>
                    {t('notices.posted_by')} {n.created_by_name || '—'} · {fmtDate(n.created_at)}
                    {n.updated_at && <> · {t('notices.edited')} {fmtDate(n.updated_at)}</>}
                  </p>
                </div>
                {canEdit(n) && (
                  <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                    <button className="btn" style={{ padding: '4px 12px', fontSize: '.75rem', background: 'var(--blue)', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }} onClick={() => startEdit(n)}>
                      ✏️ {t('notices.edit')}
                    </button>
                    <button className="btn" style={{ padding: '4px 12px', fontSize: '.75rem', background: 'var(--gray-300)', color: 'var(--red)', border: 'none', borderRadius: 4, cursor: 'pointer' }} onClick={() => remove(n)}>
                      🗑️
                    </button>
                  </div>
                )}
              </div>
              <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '.9rem' }}>{n.body}</p>
            </div>
          ))
        )}
      </div>
    </>
  )
}
