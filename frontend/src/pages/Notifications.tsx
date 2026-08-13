import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import NavBar from '../components/NavBar'

interface EmailConfigData {
  enabled: boolean
  transport_mode: string
  from_name: string | null
  from_email: string | null
  reply_to: string | null
  signature: string | null
  smtp_host: string | null
  smtp_port: number
  smtp_user: string | null
  has_smtp_password: boolean
  smtp_password?: string
  smtp_use_tls: boolean
  smtp_use_ssl: boolean
  direction_email: string | null
  remind_days_before: number
}

interface OutboxMessage {
  id: number
  event_type: string
  transport: string
  recipient_name: string | null
  recipient_email: string
  lang: string
  subject: string
  status: string
  attempts: number
  last_error: string | null
  has_eml: boolean
  created_at: string | null
  sent_at: string | null
}

const EVENT_LABELS: Record<string, string> = {
  meeting_invite: '📅 Convocation',
  meeting_reminder: '⏰ Rappel réunion',
  minutes_direction: '📤 PV → direction',
  minutes_dp: '📣 PV → délégation',
  member_invite: '🎟️ Invitation membre',
  test: '🧪 Test',
}

const STATUS_LABELS: Record<string, string> = {
  ready: '⏳ Prêt',
  sent: '✅ Envoyé',
  failed: '❌ Échec',
  cancelled: '🚫 Annulé',
}

export default function Notifications() {
  const { token, user } = useAuth()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'

  const [cfg, setCfg] = useState<EmailConfigData | null>(null)
  const [msgs, setMsgs] = useState<OutboxMessage[]>([])
  const [testRecipient, setTestRecipient] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    // user peut être null au premier rendu (profil chargé en async) :
    // ne pas rediriger avant la fin du chargement
    if (user === null) return
    if (!isAdmin) { navigate('/dashboard'); return }
    load()
  }, [user, isAdmin])

  async function load() {
    const h = { Authorization: `Bearer ${token}` }
    try {
      const [c, m] = await Promise.all([
        fetch('/api/emails/config', { headers: h }),
        fetch('/api/emails', { headers: h }),
      ])
      if (c.ok) setCfg(await c.json())
      if (m.ok) setMsgs(await m.json())
    } catch (e: any) {
      setErr(e.message)
    }
  }

  const set = useCallback((patch: Partial<EmailConfigData>) => {
    setCfg(prev => prev ? { ...prev, ...patch } : prev)
  }, [])

  async function saveConfig(e: FormEvent) {
    e.preventDefault()
    if (!cfg) return
    setSaving(true); setErr(null); setMsg(null)
    try {
      const r = await fetch('/api/emails/config', {
        method: 'PUT',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Erreur')
      setCfg(await r.json())
      setMsg('Configuration enregistrée ✅')
    } catch (ex: any) {
      setErr(ex.message)
    } finally {
      setSaving(false)
    }
  }

  async function sendTest() {
    if (!testRecipient) return
    setErr(null); setMsg(null)
    try {
      const r = await fetch('/api/emails/config/test', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ recipient: testRecipient }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Erreur')
      setMsg(`Email de test : ${data.detail}`)
      load()
    } catch (ex: any) {
      setErr(ex.message)
    }
  }

  async function action(id: number, path: string) {
    setErr(null)
    try {
      const r = await fetch(`/api/emails/${id}${path}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Erreur')
      load()
    } catch (ex: any) {
      setErr(ex.message)
    }
  }

  async function downloadEml(id: number) {
    const r = await fetch(`/api/emails/${id}/download.eml`, { headers: { Authorization: `Bearer ${token}` } })
    if (!r.ok) return
    const blob = await r.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `notification-${id}.eml`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function exportExternal() {
    setErr(null)
    try {
      const r = await fetch('/api/emails/export', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Erreur')
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'notifications-export.zip'
      a.click()
      URL.revokeObjectURL(url)
      setMsg('Export généré — exécutez email_sender.py sur la machine avec accès SMTP')
      load()
    } catch (ex: any) {
      setErr(ex.message)
    }
  }

  if (!cfg) return <><NavBar /><div className="dashboard"><div className="spinner" /></div></>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <h2>📧 Notifications par email</h2>
          <p style={{ color: 'var(--gray-600)', fontSize: '.85rem', marginBottom: 16 }}>
            Les événements de l'application (convocations, PV, invitations, rappels) sont mis en file
            puis acheminés selon le mode choisi. L'administrateur de la délégation configure tout ici —
            aucune infrastructure externe n'est requise.
          </p>
          <form onSubmit={saveConfig}>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" checked={cfg.enabled} onChange={e => set({ enabled: e.target.checked })} />
                Activer les notifications
              </label>
            </div>

            <div className="form-group">
              <label>Mode d'acheminement</label>
              <select value={cfg.transport_mode} onChange={e => set({ transport_mode: e.target.value })}>
                <option value="eml">📄 Fichiers .eml (téléchargement — aucun SMTP requis)</option>
                <option value="smtp">📨 Serveur SMTP (envoi direct)</option>
                <option value="external">🌐 Standalone (export JSON + CLI sur une autre machine)</option>
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div className="form-group">
                <label>Nom de l'expéditeur</label>
                <input value={cfg.from_name || ''} onChange={e => set({ from_name: e.target.value })} placeholder="Délégation du personnel" />
              </div>
              <div className="form-group">
                <label>Email de l'expéditeur</label>
                <input value={cfg.from_email || ''} onChange={e => set({ from_email: e.target.value })} placeholder="delegation@entreprise.lu" />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
              <div className="form-group">
                <label>Email de la direction</label>
                <input value={cfg.direction_email || ''} onChange={e => set({ direction_email: e.target.value })} placeholder="direction@entreprise.lu" />
                <small style={{ color: 'var(--gray-500)' }}>Reçoit les convocations (réunion avec direction) et les liens de lecture des PV.</small>
              </div>
              <div className="form-group">
                <label>Rappel avant réunion (jours)</label>
                <input type="number" min={0} max={30} value={cfg.remind_days_before} onChange={e => set({ remind_days_before: parseInt(e.target.value) || 3 })} />
              </div>
            </div>

            <div className="form-group">
              <label>Signature (optionnelle)</label>
              <textarea value={cfg.signature || ''} onChange={e => set({ signature: e.target.value })} rows={2} placeholder="Cordialement, le bureau de la délégation" />
            </div>

            {cfg.transport_mode === 'smtp' && (
              <div style={{ background: 'var(--gray-100)', padding: '16px', borderRadius: 8, marginBottom: 16 }}>
                <h3 style={{ fontSize: '.9rem', marginBottom: 12 }}>🖧 Paramètres SMTP</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '0 16px' }}>
                  <div className="form-group">
                    <label>Hôte</label>
                    <input value={cfg.smtp_host || ''} onChange={e => set({ smtp_host: e.target.value })} placeholder="smtp.example.com" />
                  </div>
                  <div className="form-group">
                    <label>Port</label>
                    <input type="number" value={cfg.smtp_port} onChange={e => set({ smtp_port: parseInt(e.target.value) || 587 })} />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                  <div className="form-group">
                    <label>Utilisateur (optionnel)</label>
                    <input value={cfg.smtp_user || ''} onChange={e => set({ smtp_user: e.target.value })} placeholder="robot@entreprise.lu" />
                  </div>
                  <div className="form-group">
                    <label>Mot de passe {cfg.has_smtp_password ? '(remplacé si saisi)' : ''}</label>
                    <input type="password" value="" onChange={e => set({ smtp_password: e.target.value })} placeholder={cfg.has_smtp_password ? '••••••••' : 'Mot de passe'} autoComplete="new-password" />
                  </div>
                </div>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <input type="checkbox" checked={cfg.smtp_use_tls} onChange={e => set({ smtp_use_tls: e.target.checked })} />
                  STARTTLS (port 587)
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <input type="checkbox" checked={cfg.smtp_use_ssl} onChange={e => set({ smtp_use_ssl: e.target.checked })} />
                  SSL direct (port 465)
                </label>
              </div>
            )}

            <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? <div className="spinner" /> : 'Enregistrer'}
              </button>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  type="email"
                  placeholder="destinataire du test"
                  value={testRecipient}
                  onChange={e => setTestRecipient(e.target.value)}
                  style={{ padding: '8px', borderRadius: 6, border: '1px solid var(--gray-300)' }}
                />
                <button type="button" className="btn" onClick={sendTest} disabled={!cfg.enabled || !testRecipient}>
                  🧪 Envoyer un test
                </button>
              </div>
            </div>
          </form>
        </div>

        <div className="card mb-24">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h2 style={{ margin: 0 }}>📮 Messages (outbox)</h2>
            {cfg.transport_mode === 'external' && (
              <button className="btn" onClick={exportExternal}>📦 Exporter pour la CLI</button>
            )}
          </div>
          {msgs.length === 0 ? (
            <p style={{ color: 'var(--gray-600)', textAlign: 'center', padding: 24 }}>
              Aucun message pour l'instant — les notifications seront listées ici.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Type</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Destinataire</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Sujet</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Statut</th>
                    <th style={{ padding: '8px', textAlign: 'left' }}>Date</th>
                    <th style={{ padding: '8px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {msgs.map(m => (
                    <tr key={m.id} style={{ borderBottom: '1px solid var(--gray-200)' }}>
                      <td style={{ padding: '8px' }}>{EVENT_LABELS[m.event_type] || m.event_type}</td>
                      <td style={{ padding: '8px' }}>{m.recipient_email}</td>
                      <td style={{ padding: '8px', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.subject}>{m.subject}</td>
                      <td style={{ padding: '8px' }}>
                        <span style={{
                          background: m.status === 'sent' ? '#d4edda' : m.status === 'failed' ? '#fdecea' : m.status === 'cancelled' ? 'var(--gray-100)' : '#fff3cd',
                          color: m.status === 'sent' ? 'var(--green)' : m.status === 'failed' ? 'var(--red)' : 'var(--gray-700)',
                          padding: '2px 10px', borderRadius: 4, fontWeight: 600, fontSize: '.75rem', whiteSpace: 'nowrap',
                        }}>
                          {STATUS_LABELS[m.status] || m.status}
                        </span>
                        {m.last_error && <div style={{ color: 'var(--red)', fontSize: '.7rem', marginTop: 2 }} title={m.last_error}>{m.last_error.slice(0, 60)}</div>}
                      </td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap' }}>
                        {m.created_at ? new Date(m.created_at).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                      </td>
                      <td style={{ padding: '8px', whiteSpace: 'nowrap', textAlign: 'right' }}>
                        {m.has_eml && <button className="btn" style={{ marginRight: 4, padding: '4px 10px', fontSize: '.75rem' }} onClick={() => downloadEml(m.id)}>⬇️ .eml</button>}
                        {m.status === 'failed' && <button className="btn" style={{ marginRight: 4, padding: '4px 10px', fontSize: '.75rem' }} onClick={() => action(m.id, '/retry')}>↻ Réessayer</button>}
                        {m.status === 'ready' && (
                          <>
                            {m.transport === 'external' && <button className="btn" style={{ marginRight: 4, padding: '4px 10px', fontSize: '.75rem' }} onClick={() => action(m.id, '/mark-sent')}>✓ Marquer envoyé</button>}
                            <button className="btn" style={{ padding: '4px 10px', fontSize: '.75rem' }} onClick={() => action(m.id, '/cancel')}>Annuler</button>
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
