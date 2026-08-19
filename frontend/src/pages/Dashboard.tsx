import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useVault } from '../hooks/useVault'
import NavBar from '../components/NavBar'
import { useT } from '../i18n/I18nContext'
import * as api from '../api/client'
import type { InvitationResponse } from '../api/client'
import { groupCode } from '../lib/vaultSession'
import { getSessionDEK, deriveKEKFromCode, DEFAULT_KDF_PARAMS } from '../lib/vault'

export default function Dashboard() {
  const { t } = useT()
  const { user, organization, fetchDashboard } = useAuth()
  const { status } = useVault()

  // Invitation form state
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({
    email: '', first_name: '', last_name: '',
    delegue_status: 'titulaire', delegue_role: 'membre',
    is_delegue_securite_sante: false, is_delegue_egalite: false,
  })
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteLoading, setInviteLoading] = useState(false)

  // One-time code display
  const [generatedCode, setGeneratedCode] = useState<string | null>(null)
  const [codeCopied, setCodeCopied] = useState(false)
  const [vaultAttached, setVaultAttached] = useState(false)

  // Active invitations list
  const [invitations, setInvitations] = useState<InvitationResponse[]>([])

  // ── Invitation en masse ──
  const [batchText, setBatchText] = useState('')
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<api.BatchInviteResponse | null>(null)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [batchCopied, setBatchCopied] = useState<string | null>(null)

  // ── Vitrine widgets ──
  const [meetingStats, setMeetingStats] = useState<any>(null)
  const [nextMeeting, setNextMeeting] = useState<any>(null)
  const [consultStats, setConsultStats] = useState<any>(null)
  const [timeSummary, setTimeSummary] = useState<any>(null)
  const [workforce, setWorkforce] = useState<any>(null)
  const [members, setMembers] = useState<any[]>([])

  useEffect(() => {
    if (!user) return
    const h = { Authorization: 'Bearer ' + localStorage.getItem('token') }
    const month = new Date().toISOString().slice(0, 7)
    fetch('/api/meetings/stats', { headers: h }).then(r => r.json()).then(setMeetingStats).catch(() => {})
    fetch('/api/consultations/stats', { headers: h }).then(r => r.json()).then(setConsultStats).catch(() => {})
    fetch(`/api/time/summary?month=${month}`, { headers: h }).then(r => r.json()).then(setTimeSummary).catch(() => {})
    fetch('/api/workforce-stats/latest', { headers: h }).then(r => r.json()).then(setWorkforce).catch(() => {})
    fetch('/api/organization/members', { headers: h }).then(r => r.json()).then(setMembers).catch(() => {})
    fetch('/api/meetings', { headers: h })
      .then(r => r.json())
      .then(list => {
        const now = new Date().toISOString()
        const upcoming = list
          .filter((m: any) => m.date >= now && m.status !== 'cancelled')
          .sort((a: any, b: any) => a.date.localeCompare(b.date))
        setNextMeeting(upcoming[0] ?? null)
      })
      .catch(() => {})
  }, [user])

  useEffect(() => { if (!user) fetchDashboard() }, [])

  // Load invitations
  useEffect(() => {
    if (user?.role === 'admin') {
      api.listInvitations().then(setInvitations).catch(() => {})
    }
  }, [user])

  async function handleInvite(e: FormEvent) {
    e.preventDefault()
    setInviteError(null)
    setGeneratedCode(null)
    setVaultAttached(false)

    // If vault is active, inviter must have it unlocked
    if (status === 'locked') {
      setInviteError(t('dashboard.invite_vault_blocked'))
      return
    }

    setInviteLoading(true)
    try {
      // Step 1: Create invitation (without vault_envelope first — we need the code)
      const result = await api.createInvitation({
        ...inviteForm,
      })

      setGeneratedCode(groupCode(result.code))
      setCodeCopied(false)

      // Step 2: If vault is active, attach the vault envelope using the code
      if (status === 'unlocked') {
        const dek = getSessionDEK()
        if (dek) {
          const normalized = result.code // raw code from server, no dashes/spaces
          const salt = crypto.getRandomValues(new Uint8Array(16))
          const kek = await deriveKEKFromCode(normalized, salt, DEFAULT_KDF_PARAMS)
          const nonce = crypto.getRandomValues(new Uint8Array(12))
          const wrapped = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv: nonce },
            kek,
            dek,
          )

          await api.attachInvitationEnvelope(result.id, {
            wrapped_dek: btoa(String.fromCharCode(...new Uint8Array(wrapped))),
            nonce: btoa(String.fromCharCode(...nonce)),
            kdf_salt: btoa(String.fromCharCode(...salt)),
            kdf_params: JSON.stringify(DEFAULT_KDF_PARAMS),
          })
          setVaultAttached(true)
        }
      }

      // Refresh invitations list
      const list = await api.listInvitations()
      setInvitations(list)
    } catch (e: any) {
      setInviteError(e.message)
      // If vault attachment failed but invitation was created, still show the code
    } finally {
      setInviteLoading(false)
    }
  }

  async function copyCode() {
    if (generatedCode) {
      await navigator.clipboard.writeText(generatedCode.replace(/-/g, ''))
      setCodeCopied(true)
      setTimeout(() => setCodeCopied(false), 2000)
    }
  }

  function updateInvite(field: string, value: any) {
    setInviteForm(prev => ({ ...prev, [field]: value }))
  }

  // ── Invitation en masse ──
  function parseBatchLines(text: string): { email: string; first_name: string; last_name: string }[] {
    return text.split('\n')
      .map(l => l.trim())
      .filter(l => l.length > 0)
      .map(line => {
        const sep = line.includes(';') ? ';' : ','
        const parts = line.split(sep).map(p => p.trim())
        return { email: parts[0] || '', first_name: parts[1] || '', last_name: parts[2] || '' }
      })
  }

  async function handleBatchInvite() {
    setBatchError(null)
    setBatchResult(null)
    const items = parseBatchLines(batchText)
    if (items.length === 0) { setBatchError(t('dashboard.batch_empty')); return }
    setBatchLoading(true)
    try {
      const res = await api.createInvitationsBatch(items)
      setBatchResult(res)
      const list = await api.listInvitations()
      setInvitations(list)
    } catch (e: any) {
      setBatchError(e.message)
    } finally {
      setBatchLoading(false)
    }
  }

  async function copyBatchCode(code: string) {
    await navigator.clipboard.writeText(code.replace(/-/g, ''))
    setBatchCopied(code)
    setTimeout(() => setBatchCopied(null), 2000)
  }

  if (!user || !organization) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {/* ── Vitrine : vue d'ensemble ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 24 }}>
          {/* Réunions */}
          <div className="card" style={{ borderTop: '4px solid var(--blue)' }}>
            <h3 style={{ marginTop: 0, fontSize: '.95rem' }}>📅 {t('dashboard.widget_meetings')}</h3>
            {meetingStats ? (
              <>
                <p style={{ margin: '6px 0', fontSize: '1.6rem', fontWeight: 700 }}>
                  {meetingStats.total}<span style={{ fontSize: '.85rem', fontWeight: 400, color: 'var(--gray-600)' }}> / {meetingStats.min_required} / an</span>
                </p>
                <p style={{ margin: 0, fontSize: '.8rem', color: 'var(--gray-600)' }}>
                  {t('dashboard.widget_with_direction')} : {meetingStats.with_direction} / {meetingStats.min_with_direction}
                </p>
              </>
            ) : <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>—</p>}
            {nextMeeting && (
              <p style={{ margin: '8px 0 0', fontSize: '.8rem', color: 'var(--gray-600)' }}>
                📌 {nextMeeting.title} — {new Date(nextMeeting.date).toLocaleDateString()}
              </p>
            )}
          </div>

          {/* Consultations */}
          <div className="card" style={{ borderTop: '4px solid #b45309' }}>
            <h3 style={{ marginTop: 0, fontSize: '.95rem' }}>📋 {t('dashboard.widget_consultations')}</h3>
            {consultStats ? (
              <>
                <p style={{ margin: '6px 0', fontSize: '1.6rem', fontWeight: 700 }}>
                  {consultStats.pending}
                  {consultStats.overdue > 0 && (
                    <span style={{ marginLeft: 8, background: '#fee2e2', color: '#b91c1c', borderRadius: 999, padding: '2px 10px', fontSize: '.8rem', fontWeight: 600 }}>
                      ⚠️ {consultStats.overdue} {t('dashboard.widget_overdue')}
                    </span>
                  )}
                </p>
                <p style={{ margin: 0, fontSize: '.8rem', color: 'var(--gray-600)' }}>
                  {t('dashboard.widget_received')} : {consultStats.received} · {t('dashboard.widget_closed')} : {consultStats.closed}
                </p>
              </>
            ) : <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>—</p>}
          </div>

          {/* Heures */}
          <div className="card" style={{ borderTop: '4px solid #047857' }}>
            <h3 style={{ marginTop: 0, fontSize: '.95rem' }}>⏱️ {t('dashboard.widget_hours')}</h3>
            {timeSummary ? (
              <>
                <p style={{ margin: '6px 0', fontSize: '1.6rem', fontWeight: 700 }}>
                  {timeSummary.total_hours}<span style={{ fontSize: '.85rem', fontWeight: 400, color: 'var(--gray-600)' }}> h</span>
                </p>
                <p style={{ margin: 0, fontSize: '.8rem', color: 'var(--gray-600)' }}>
                  {t('dashboard.widget_credit')} : {timeSummary.credit_hours} h
                </p>
              </>
            ) : <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>—</p>}
          </div>

          {/* Effectif par sexe */}
          <div className="card" style={{ borderTop: '4px solid #db2777' }}>
            <h3 style={{ marginTop: 0, fontSize: '.95rem' }}>👥 {t('dashboard.widget_workforce')}</h3>
            {workforce ? (
              <>
                <p style={{ margin: '6px 0', fontSize: '1.6rem', fontWeight: 700 }}>
                  {workforce.total}<span style={{ fontSize: '.85rem', fontWeight: 400, color: 'var(--gray-600)' }}> {t('dashboard.widget_people')}</span>
                </p>
                <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: '#e5e7eb', marginBottom: 4 }}>
                  <div style={{ width: `${workforce.total ? (workforce.male_count / workforce.total) * 100 : 0}%`, background: '#2563eb' }} />
                  <div style={{ width: `${workforce.total ? (workforce.female_count / workforce.total) * 100 : 0}%`, background: '#db2777' }} />
                </div>
                <p style={{ margin: 0, fontSize: '.75rem', color: 'var(--gray-600)' }}>
                  👨 {workforce.male_count} · 👩 {workforce.female_count} <span style={{ opacity: .7 }}>({workforce.semester})</span>
                </p>
              </>
            ) : <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>—</p>}
          </div>

          {/* Membres */}
          <div className="card" style={{ borderTop: '4px solid #6d28d9' }}>
            <h3 style={{ marginTop: 0, fontSize: '.95rem' }}>🧑‍🤝‍🧑 {t('dashboard.widget_members')}</h3>
            {members.length > 0 ? (
              <>
                <p style={{ margin: '6px 0', fontSize: '1.6rem', fontWeight: 700 }}>{members.length}</p>
                <p style={{ margin: 0, fontSize: '.8rem', color: 'var(--gray-600)' }}>
                  {t('dashboard.widget_titulaires')} : {members.filter((m: any) => m.delegue_status === 'titulaire').length} · {t('dashboard.widget_suppleants')} : {members.filter((m: any) => m.delegue_status === 'suppleant').length}
                </p>
              </>
            ) : <p style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>—</p>}
          </div>
        </div>

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

        {/* ── Invitation section (admin only) ── */}
        {user.role === 'admin' && (
          <>
            <div className="card mb-24">
              <h2>{t('dashboard.invite')}</h2>
              <p className="subtitle">{t('dashboard.invite_subtitle')}</p>

              {/* Vault blocked warning */}
              {status === 'locked' && !showInvite && (
                <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: '.85rem' }}>
                  ⚠️ {t('dashboard.invite_vault_blocked')}
                </div>
              )}

              {!showInvite ? (
                <button
                  className="btn btn-primary"
                  onClick={() => { setShowInvite(true); setGeneratedCode(null); setInviteError(null) }}
                  disabled={status === 'locked'}
                >
                  {t('dashboard.invite_generate')}
                </button>
              ) : (
                <form onSubmit={handleInvite}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                    <div className="form-group"><label>{t('join.firstname')}</label><input value={inviteForm.first_name} onChange={e => updateInvite('first_name', e.target.value)} required /></div>
                    <div className="form-group"><label>{t('join.lastname')}</label><input value={inviteForm.last_name} onChange={e => updateInvite('last_name', e.target.value)} required /></div>
                  </div>
                  <div className="form-group"><label>{t('join.email')}</label><input type="email" value={inviteForm.email} onChange={e => updateInvite('email', e.target.value)} required /></div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
                    <div className="form-group">
                      <label>{t('dashboard.invite_status')}</label>
                      <select value={inviteForm.delegue_status} onChange={e => updateInvite('delegue_status', e.target.value)}>
                        {api.DELEGUE_STATUS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label>{t('dashboard.invite_role')}</label>
                      <select value={inviteForm.delegue_role} onChange={e => updateInvite('delegue_role', e.target.value)}>
                        {api.DELEGUE_ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="form-group" style={{ display: 'flex', gap: 24 }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 400, fontSize: '.85rem' }}>
                      <input type="checkbox" checked={inviteForm.is_delegue_securite_sante} onChange={e => updateInvite('is_delegue_securite_sante', e.target.checked)} />
                      {t('dashboard.invite_secu')}
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 400, fontSize: '.85rem' }}>
                      <input type="checkbox" checked={inviteForm.is_delegue_egalite} onChange={e => updateInvite('is_delegue_egalite', e.target.checked)} />
                      {t('dashboard.invite_egalite')}
                    </label>
                  </div>

                  {inviteError && <div className="error-msg">{inviteError}</div>}

                  <div style={{ display: 'flex', gap: 12 }}>
                    <button type="submit" className="btn btn-primary" disabled={inviteLoading}>
                      {inviteLoading ? <div className="spinner" /> : t('dashboard.invite_generate')}
                    </button>
                    <button type="button" className="btn" onClick={() => { setShowInvite(false); setInviteError(null) }} style={{ background: 'var(--gray-300)' }}>
                      {t('organigramme.cancel')}
                    </button>
                  </div>
                </form>
              )}

              {/* One-time code display */}
              {generatedCode && (
                <div style={{
                  marginTop: 16,
                  padding: 12,
                  background: '#fff3cd',
                  border: '2px solid #ffc107',
                  borderRadius: 8,
                }}>
                  <h3 style={{ marginTop: 0, color: '#856404' }}>⚠️ {t('dashboard.invite_code_once_title')}</h3>
                  <p style={{ fontSize: '.85rem', color: '#856404', marginBottom: 8 }}>
                    {t('dashboard.invite_code_once_warning')}
                  </p>
                  <div style={{
                    fontFamily: 'monospace',
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    letterSpacing: 2,
                    background: '#fff',
                    padding: '12px 16px',
                    borderRadius: 6,
                    border: '1px solid #ddd',
                    textAlign: 'center',
                    marginBottom: 8,
                  }}>
                    {generatedCode}
                  </div>
                  <button
                    className="btn"
                    onClick={copyCode}
                    style={{ background: 'var(--blue)', color: '#fff', border: 'none' }}
                  >
                    {codeCopied ? t('dashboard.invite_code_copied') : t('dashboard.invite_code_copy')}
                  </button>
                  {vaultAttached && (
                    <p style={{ color: 'var(--green)', fontSize: '.85rem', marginTop: 8 }}>
                      {t('vault.envelope_sent')}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* ── Invitation en masse ── */}
            <div className="card mb-24">
              <h2>{t('dashboard.batch_title')}</h2>
              <p className="subtitle">{t('dashboard.batch_subtitle')}</p>
              <textarea
                value={batchText}
                onChange={e => setBatchText(e.target.value)}
                rows={6}
                placeholder={t('dashboard.batch_placeholder')}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: '.85rem', padding: 10, borderRadius: 6, border: '1px solid var(--gray-300)', marginBottom: 8 }}
              />
              <p style={{ fontSize: '.8rem', color: 'var(--gray-600)', marginBottom: 8 }}>
                {t('dashboard.batch_vault_note')}
              </p>
              {batchError && <div className="error-msg">{batchError}</div>}
              <button className="btn btn-primary" onClick={handleBatchInvite} disabled={batchLoading}>
                {batchLoading ? <div className="spinner" /> : t('dashboard.batch_generate')}
              </button>

              {batchResult && (
                <div style={{ marginTop: 16 }}>
                  <p style={{ fontSize: '.9rem', fontWeight: 600 }}>
                    ✅ {batchResult.created} {t('dashboard.batch_count_created')}
                    {batchResult.skipped > 0 && <> · ⚠️ {batchResult.skipped} {t('dashboard.batch_count_skipped')}</>}
                    {batchResult.failed > 0 && <> · ❌ {batchResult.failed} {t('dashboard.batch_count_failed')}</>}
                  </p>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.8rem', marginTop: 8 }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                        <th style={{ padding: 6, textAlign: 'left' }}>{t('join.email')}</th>
                        <th style={{ padding: 6, textAlign: 'left' }}>{t('dashboard.batch_result')}</th>
                        <th style={{ padding: 6, textAlign: 'left' }}>{t('dashboard.invite_code')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {batchResult.results.map((r, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                          <td style={{ padding: 6 }}>{r.email}</td>
                          <td style={{ padding: 6 }}>
                            {r.status === 'created' && <span style={{ color: 'var(--green)' }}>✅ {t('dashboard.batch_created')}</span>}
                            {r.status === 'duplicate' && <span style={{ color: '#b45309' }}>⚠️ {r.message}</span>}
                            {r.status === 'invalid' && <span style={{ color: 'var(--red)' }}>❌ {r.message}</span>}
                          </td>
                          <td style={{ padding: 6 }}>
                            {r.invitation?.code && (
                              <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '.75rem' }}>
                                {groupCode(r.invitation.code)}
                                <button
                                  className="btn"
                                  onClick={() => copyBatchCode(r.invitation!.code!)}
                                  style={{ marginLeft: 8, padding: '2px 10px', fontSize: '.72rem', background: 'var(--blue)', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                                >
                                  {batchCopied === r.invitation.code ? t('dashboard.invite_code_copied') : t('dashboard.invite_code_copy')}
                                </button>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Active invitations */}
            {invitations.length > 0 && (
              <div className="card mb-24">
                <h2>{t('dashboard.invitations_active')}</h2>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                      <th style={{ padding: '8px', textAlign: 'left' }}>{t('dashboard.invite_member')}</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>{t('join.email')}</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>{t('dashboard.invite_status')}</th>
                      <th style={{ padding: '8px', textAlign: 'left' }}>{t('dashboard.invite_role')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invitations.map(inv => (
                      <tr key={inv.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                        <td style={{ padding: '8px' }}>{inv.first_name} {inv.last_name}</td>
                        <td style={{ padding: '8px' }}>{inv.email}</td>
                        <td style={{ padding: '8px' }}>{inv.delegue_status}</td>
                        <td style={{ padding: '8px' }}>{inv.delegue_role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}
