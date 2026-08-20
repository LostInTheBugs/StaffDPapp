import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useVault } from '../hooks/useVault'
import NavBar from '../components/NavBar'
import VaultCreate from '../components/VaultCreate'
import RecoveryKeyManager from '../components/RecoveryKeyManager'
import * as api from '../api/client'
import { useT } from '../i18n/I18nContext'

interface Member {
  id: number; full_name: string; role: string; delegue_status: string; delegue_role: string
}

export default function EditOrganization() {
  const { user, organization, setAuth, token } = useAuth()
  const { status } = useVault()
  const { t } = useT()
  const navigate = useNavigate()
  const isAdmin = user?.role === 'admin'
  const isBureau = user?.delegue_role === 'president' || user?.delegue_role === 'vice_president' || user?.delegue_role === 'secretaire'

  const [form, setForm] = useState({
    name: organization?.name || '',
    company_name: organization?.company_name || '',
    employee_count: organization?.employee_count || 15,
    mandate_end_date: organization?.mandate_end_date || '',
    contact_email: organization?.contact_email || '',
    contact_phone: organization?.contact_phone || '',
    contact_hours: organization?.contact_hours || '',
  })
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [modules, setModules] = useState<string[]>(organization?.enabled_modules || [])
  const [logoData, setLogoData] = useState<string | null>(organization?.logo_data || null)
  const [logoFile, setLogoFile] = useState<File | null>(null)

  useEffect(() => {
    if (!isAdmin) { navigate('/dashboard'); return }
    loadMembers()
    if (organization?.enabled_modules?.length) setModules(organization.enabled_modules)
    if (organization?.logo_data) setLogoData(organization.logo_data)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadMembers() {
    try {
      const res = await fetch('/api/organization/members', { headers: { Authorization: `Bearer ${token}` } })
      setMembers(await res.json())
    } catch { /* */ }
  }

  async function updateOrg(e: FormEvent) {
    e.preventDefault(); setErr(null)
    if (form.employee_count < 15) { setErr('Minimum 15 salariés'); return }
    try {
      const data: any = { ...form }
      if (!data.mandate_end_date) delete data.mandate_end_date
      const updated = await api.updateOrganization(data)
      setAuth(token!, user!, updated)
      setMsg('Organisation mise à jour ✅')
    } catch (e: any) { setErr(e.message) }
  }

  async function toggleRole(member: Member) {
    if (!isAdmin) return
    const newRole = member.role === 'admin' ? 'member' : 'admin'
    try {
      await fetch(`/api/organization/members/${member.id}/role`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
        body: JSON.stringify({ role: newRole }),
      })
      setMembers(prev => prev.map(m => m.id === member.id ? { ...m, role: newRole } : m))
    } catch (e: any) { setErr(e.message) }
  }

  async function removeMember(member: Member) {
    if (!isAdmin) return
    if (!confirm(`Retirer ${member.full_name} de l'organisation ?\n\nSon compte sera désactivé (connexion bloquée), mais l'historique (PV, heures, réunions) sera conservé.`)) return
    setErr(null)
    try {
      await api.removeMember(member.id)
      setMsg(`✅ ${member.full_name} a été retiré(e) de l'organisation`)
      loadMembers()
    } catch (e: any) { setErr(e.message) }
  }

  async function saveContact() {
    setErr(null)
    try {
      const updated = await api.updateOrganization({
        contact_email: form.contact_email,
        contact_phone: form.contact_phone,
        contact_hours: form.contact_hours,
      })
      setAuth(token!, user!, updated)
      setMsg(t('org.contact_saved'))
    } catch (e: any) { setErr(e.message) }
  }

  async function saveModules() {
    setErr(null)
    try {
      const updated = await api.updateModules(modules)
      setAuth(token!, user!, updated)
      setMsg('Modules mis à jour ✅')
    } catch (e: any) { setErr(e.message) }
  }

  function toggleModule(m: string) {
    setModules(prev => prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m])
  }

  function onLogoFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 512 * 1024) { setErr('Logo trop volumineux (max 512 Ko)'); return }
    const reader = new FileReader()
    reader.onload = () => {
      const dataUrl = reader.result as string
      if (!dataUrl.startsWith('data:image/')) { setErr('Format invalide : choisissez une image (PNG, JPG, SVG…)'); return }
      setLogoData(dataUrl)
      setLogoFile(file)
    }
    reader.readAsDataURL(file)
  }

  async function saveLogo() {
    if (!logoData) return
    setErr(null)
    try {
      const updated = await api.updateLogo(logoData)
      setAuth(token!, user!, updated)
      setLogoFile(null)
      setMsg('Logo enregistré ✅')
    } catch (e: any) { setErr(e.message) }
  }

  async function removeLogo() {
    setErr(null)
    try {
      const updated = await api.deleteLogo()
      setAuth(token!, user!, updated)
      setLogoData(null)
      setLogoFile(null)
      setMsg('Logo supprimé')
    } catch (e: any) { setErr(e.message) }
  }

  return (
    <>
      <NavBar />
      <div className="dashboard">
        {msg && <div className="success-msg">{msg}</div>}
        {err && <div className="error-msg">{err}</div>}

        <div className="card mb-24">
          <h2>🏢 Mon organisation</h2>
          <form onSubmit={updateOrg}>
            <div className="form-group"><label>Nom de la délégation *</label><input value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} required /></div>
            <div className="form-group"><label>Nom officiel de l'entreprise</label><input value={form.company_name} onChange={e => setForm(p => ({ ...p, company_name: e.target.value }))} /></div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0 16px' }}>
              <div className="form-group"><label>Effectif *</label><input type="number" min={15} value={form.employee_count} onChange={e => setForm(p => ({ ...p, employee_count: parseInt(e.target.value) || 15 }))} required /></div>
              <div className="form-group"><label>Date de fin de mandat</label><input type="date" value={form.mandate_end_date} onChange={e => setForm(p => ({ ...p, mandate_end_date: e.target.value }))} /></div>
            </div>
            <div style={{ marginTop: 8, fontSize: '.85rem', color: 'var(--gray-600)' }}>
              Identifiant de l'organisation (pour le logo sur l'écran de connexion) : <code>{organization?.slug}</code>
            </div>
            <button type="submit" className="btn btn-primary">Enregistrer</button>
          </form>
        </div>

        {/* Logo de l'entreprise */}
        <div className="card mb-24">
          <h2>🏷️ {t('org.logo_title')}</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>{t('org.logo_hint')}</p>
          {logoData && (
            <div style={{ marginBottom: 12, padding: 12, border: '1px solid var(--gray-300)', borderRadius: 8, background: '#fff', display: 'inline-block' }}>
              <img src={logoData} alt="logo" style={{ maxHeight: 80, maxWidth: 240, objectFit: 'contain' }} />
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <input type="file" accept="image/*" onChange={onLogoFile} style={{ fontSize: '.85rem' }} />
            <button className="btn btn-primary" onClick={saveLogo} disabled={!logoFile}>{t('org.logo_save')}</button>
            {logoData && <button className="btn" onClick={removeLogo} style={{ color: 'var(--red)' }}>{t('org.logo_remove')}</button>}
          </div>
        </div>

        {/* Modules activables/désactivables */}
        <div className="card mb-24">
          <h2>🧩 {t('org.modules_title')}</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>{t('org.modules_hint')}</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 8, marginBottom: 12 }}>
            {api.ALL_MODULES.map(m => (
              <label key={m} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', border: '1px solid var(--gray-300)', borderRadius: 6, cursor: 'pointer', fontSize: '.9rem', background: modules.includes(m) ? '#ebf8ff' : '#fff' }}>
                <input type="checkbox" checked={modules.includes(m)} onChange={() => toggleModule(m)} />
                {t(`modules.${m}`)}
              </label>
            ))}
          </div>
          <button className="btn btn-primary" onClick={saveModules}>{t('org.modules_save')}</button>
        </div>

        {/* Coordonnées de contact DP */}
        <div className="card mb-24">
          <h2>📇 {t('org.contact_title')}</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>{t('org.contact_hint')}</p>
          <div style={{ display: 'grid', gap: 12 }}>
            <div className="form-group"><label>{t('org.contact_email')}</label>
              <input type="email" value={form.contact_email} onChange={e => setForm(p => ({ ...p, contact_email: e.target.value }))} placeholder="dp@entreprise.lu" /></div>
            <div className="form-group"><label>{t('org.contact_phone')}</label>
              <input value={form.contact_phone} onChange={e => setForm(p => ({ ...p, contact_phone: e.target.value }))} placeholder="+352 00 00 00" /></div>
            <div className="form-group"><label>{t('org.contact_hours')}</label>
              <textarea rows={3} value={form.contact_hours} onChange={e => setForm(p => ({ ...p, contact_hours: e.target.value }))} placeholder={t('org.contact_hours_ph')} /></div>
            <div><button className="btn btn-primary" onClick={saveContact}>{t('org.contact_save')}</button></div>
          </div>
        </div>

        {/* Vault section — visible to bureau when vault is disabled */}
        {isAdmin && isBureau && status === 'disabled' && <VaultCreate />}

        {/* Show vault status when active */}
        {isAdmin && status !== 'disabled' && (
          <div className="card mb-24">
            <h2>🔐 Coffre-fort des PV</h2>
            <div className="success-msg" style={{ background: status === 'unlocked' ? '#d4edda' : '#fff3cd', borderColor: status === 'unlocked' ? 'var(--green)' : '#ffc107' }}>
              {status === 'unlocked' ? '✅ Le coffre est actif et déverrouillé. Les PV sont chiffrés de bout en bout.' :
               '🔒 Le coffre est actif. Déverrouillez-le pour accéder aux PV chiffrés.'}
            </div>
            {status === 'unlocked' && <RecoveryKeyManager />}
          </div>
        )}

        <div className="card mb-24">
          <h2>👥 Gestion des administrateurs</h2>
          <p style={{ color: 'var(--gray-600)', marginBottom: 12 }}>
            Les administrateurs peuvent modifier l'organisation et gérer les rôles.
          </p>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.85rem' }}>
            <thead><tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
              <th style={{ padding: '8px', textAlign: 'left' }}>Membre</th>
              <th style={{ padding: '8px', textAlign: 'left' }}>Statut</th>
              <th style={{ padding: '8px', textAlign: 'left' }}>Rôle</th>
              <th style={{ padding: '8px' }}></th>
            </tr></thead>
            <tbody>
              {members.map(m => (
                <tr key={m.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                  <td style={{ padding: '8px' }}>{m.full_name}</td>
                  <td style={{ padding: '8px' }}>{m.delegue_status} / {m.delegue_role}</td>
                  <td style={{ padding: '8px' }}>
                    <span style={{
                      background: m.role === 'admin' ? '#ebf8ff' : 'var(--gray-100)',
                      color: m.role === 'admin' ? 'var(--blue)' : 'var(--gray-600)',
                      padding: '2px 10px', borderRadius: 4, fontWeight: 600, fontSize: '.8rem'
                    }}>
                      {m.role === 'admin' ? '👑 Admin' : 'Membre'}
                    </span>
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>
                    <button onClick={() => toggleRole(m)}
                      style={{
                        background: m.role === 'admin' ? 'var(--red)' : 'var(--blue)',
                        color: '#fff', border: 'none', padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: '.75rem', marginRight: 6
                      }}>
                      {m.role === 'admin' ? 'Rétrograder' : 'Promouvoir admin'}
                    </button>
                    {m.id !== user?.id && (
                      <button onClick={() => removeMember(m)}
                        style={{
                          background: 'var(--gray-300)', color: 'var(--red)', border: 'none',
                          padding: '4px 12px', borderRadius: 4, cursor: 'pointer', fontSize: '.75rem'
                        }}>
                        🗑️ Retirer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
