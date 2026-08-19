import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/I18nContext'
import NavBar from '../components/NavBar'
import * as api from '../api/client'
import { generateElectionAffichePdf } from '../lib/electionAffichePdf'

const STATUS_LABEL: Record<string, string> = {
  announced: '📢',
  voting: '🗳️',
  closed: '🏁',
}

export default function Elections() {
  const { user } = useAuth()
  const { t } = useT()

  const [elections, setElections] = useState<api.Election[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)

  // création
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ title: '', election_date: '', candidate_deadline: '', notes: '' })

  // candidat
  const [candFor, setCandFor] = useState<number | null>(null)
  const [cand, setCand] = useState({ full_name: '', list_label: '', birth_date: '', hire_date: '', declared: true })

  // vote
  const [voteFor, setVoteFor] = useState<number | null>(null)
  const [voteChoice, setVoteChoice] = useState<number | null>(null)

  // résultats
  const [resultsFor, setResultsFor] = useState<number | null>(null)
  const [results, setResults] = useState<api.ElectionResults | null>(null)

  useEffect(() => { load() }, [])

  async function load() {
    try {
      setElections(await api.listElections())
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  async function createElection(e: FormEvent) {
    e.preventDefault(); setErr(null); setMsg(null)
    try {
      await api.createElection({ title: form.title, election_date: form.election_date, candidate_deadline: form.candidate_deadline || undefined, notes: form.notes || undefined })
      setShowCreate(false); setForm({ title: '', election_date: '', candidate_deadline: '', notes: '' })
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function addCandidate(e: FormEvent, electionId: number) {
    e.preventDefault(); setErr(null); setMsg(null)
    try {
      await api.addCandidate(electionId, {
        full_name: cand.full_name, list_label: cand.list_label,
        birth_date: cand.birth_date || undefined, hire_date: cand.hire_date || undefined,
        declared_not_excluded: cand.declared,
      })
      setCand({ full_name: '', list_label: '', birth_date: '', hire_date: '', declared: true })
      setCandFor(null)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function removeCandidate(electionId: number, candidateId: number) {
    if (!confirm(t('elections.candidate_delete_confirm'))) return
    try {
      await api.removeCandidate(electionId, candidateId)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function open(electionId: number) {
    if (!confirm(t('elections.open_confirm'))) return
    try {
      await api.openElection(electionId)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function vote(electionId: number) {
    if (voteChoice === null) return
    try {
      await api.castVote(electionId, voteChoice)
      setVoteFor(null); setVoteChoice(null)
      setMsg(t('elections.vote_ok'))
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function close(electionId: number) {
    if (!confirm(t('elections.close_confirm'))) return
    try {
      const res = await api.closeElection(electionId)
      setResults(res); setResultsFor(electionId)
      await load()
    } catch (ex: any) { setErr(ex.message) }
  }

  async function showResults(electionId: number) {
    try {
      setResults(await api.getElectionResults(electionId))
      setResultsFor(electionId)
    } catch (ex: any) { setErr(ex.message) }
  }

  async function downloadAffiche(e: api.Election) {
    try {
      const pdf = await generateElectionAffichePdf({
        orgName: t('elections.org'),
        title: e.title,
        electionDate: e.election_date ? new Date(e.election_date).toLocaleDateString('fr-LU') : '—',
        candidateDeadline: e.candidate_deadline ? new Date(e.candidate_deadline).toLocaleDateString('fr-LU') : null,
        seats: 5,
        notes: e.notes,
      })
      const blob = new Blob([pdf], { type: 'application/pdf' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `affiche-elections-${e.id}.pdf`
      a.click()
      URL.revokeObjectURL(a.href)
    } catch (ex: any) { setErr(ex.message) }
  }

  function fmt(iso: string | null) {
    return iso ? new Date(iso).toLocaleDateString() : '—'
  }

  if (!user) return <div className="dashboard"><div className="spinner" /></div>

  return (
    <>
      <NavBar />
      <div className="dashboard">
        <h1 style={{ fontSize: '1.4rem' }}>🗳️ {t('elections.title')}</h1>
        <p className="subtitle" style={{ color: 'var(--gray-600)', fontSize: '.85rem' }}>
          {t('elections.subtitle')} — <em>Art. L.413-1 à L.413-6</em>
        </p>

        {err && <div className="error-msg">{err}</div>}
        {msg && <p style={{ color: 'var(--green)' }}>{msg}</p>}
        {loading && <div className="spinner" />}

        {elections.some(e => e.can_manage) && !showCreate && (
          <button className="btn btn-primary" onClick={() => { setShowCreate(true); setErr(null) }}>+ {t('elections.create')}</button>
        )}

        {showCreate && (
          <form onSubmit={createElection} className="card mb-24" style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <input required placeholder={t('elections.title_ph')} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} maxLength={200} />
            <label style={{ fontSize: '.8rem' }}>{t('elections.date_label')} <input required type="date" value={form.election_date} onChange={e => setForm({ ...form, election_date: e.target.value })} /></label>
            <label style={{ fontSize: '.8rem' }}>{t('elections.deadline_label')} <input type="date" value={form.candidate_deadline} onChange={e => setForm({ ...form, candidate_deadline: e.target.value })} /></label>
            <input placeholder={t('elections.notes_ph')} value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} maxLength={1000} />
            <div style={{ display: 'flex', gap: 10 }}>
              <button type="submit" className="btn btn-primary">{t('elections.create_btn')}</button>
              <button type="button" className="btn" style={{ background: 'var(--gray-300)' }} onClick={() => setShowCreate(false)}>{t('organigramme.cancel')}</button>
            </div>
          </form>
        )}

        {elections.length === 0 && !loading && (
          <p style={{ color: 'var(--gray-600)' }}>{t('elections.empty')}</p>
        )}

        {elections.map(e => (
          <div key={e.id} className="card mb-24">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.05rem' }}>
                  {STATUS_LABEL[e.status]} {e.title}
                  <span style={{ marginLeft: 8, fontSize: '.75rem', color: 'var(--gray-600)' }}>
                    {t(`elections.status_${e.status}`)} · {fmt(e.election_date)}
                  </span>
                </h3>
                <p style={{ margin: '2px 0 8px', fontSize: '.78rem', color: 'var(--gray-600)' }}>
                  {t('elections.votes_count')}: {e.votes_count} · {e.created_by_name ? `${t('notices.posted_by')} ${e.created_by_name}` : ''}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {e.status === 'announced' && e.can_manage && (
                  <>
                    <button className="btn" style={{ ...btnStyle, background: 'var(--blue)' }} onClick={() => downloadAffiche(e)}>🖨️ {t('elections.affiche')}</button>
                    <button className="btn" style={{ ...btnStyle, background: 'var(--green)', color: '#fff' }} onClick={() => open(e.id)}>🗳️ {t('elections.open')}</button>
                  </>
                )}
                {e.status === 'voting' && e.can_manage && (
                  <button className="btn" style={{ ...btnStyle, background: 'var(--red)', color: '#fff' }} onClick={() => close(e.id)}>🏁 {t('elections.close')}</button>
                )}
                {e.status === 'closed' && (
                  <button className="btn" style={{ ...btnStyle, background: 'var(--gray-600)', color: '#fff' }} onClick={() => showResults(e.id)}>📊 {t('elections.results')}</button>
                )}
              </div>
            </div>

            {/* Candidats */}
            {e.candidates.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '.82rem', marginTop: 8 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--gray-300)' }}>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('elections.candidate')}</th>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('elections.list')}</th>
                    <th style={{ padding: 6, textAlign: 'left' }}>{t('elections.eligibility')}</th>
                    {e.can_manage && e.status === 'announced' && <th style={{ padding: 6 }} />}
                  </tr>
                </thead>
                <tbody>
                  {e.candidates.map(c => (
                    <tr key={c.id} style={{ borderBottom: '1px solid var(--gray-300)' }}>
                      <td style={{ padding: 6 }}>{c.full_name}</td>
                      <td style={{ padding: 6 }}>{c.list_label}</td>
                      <td style={{ padding: 6 }}>
                        {c.eligible
                          ? <span style={{ color: 'var(--green)' }}>✅ {t('elections.eligible')}</span>
                          : <span style={{ color: '#b06000' }} title={c.eligibility_reason || ''}>⚠️ {c.eligibility_reason || t('elections.ineligible')}</span>}
                      </td>
                      {e.can_manage && e.status === 'announced' && (
                        <td style={{ padding: 6, textAlign: 'right' }}>
                          <button className="btn" style={{ fontSize: '.72rem', padding: '2px 8px', background: 'var(--gray-300)', border: 'none', borderRadius: 4, cursor: 'pointer', color: 'var(--red)' }} onClick={() => removeCandidate(e.id, c.id)}>🗑️</button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Ajout candidat (bureau, phase annonce) */}
            {e.status === 'announced' && e.can_manage && (
              <div style={{ marginTop: 10 }}>
                {candFor === e.id ? (
                  <form onSubmit={ev => addCandidate(ev, e.id)} style={{ display: 'flex', flexDirection: 'column', gap: 6, background: 'var(--gray-100)', padding: 10, borderRadius: 6 }}>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input required placeholder={t('elections.candidate_ph')} value={cand.full_name} onChange={x => setCand({ ...cand, full_name: x.target.value })} />
                      <input required placeholder={t('elections.list_ph')} value={cand.list_label} onChange={x => setCand({ ...cand, list_label: x.target.value })} />
                    </div>
                    <div style={{ display: 'flex', gap: 8, fontSize: '.8rem' }}>
                      <label>{t('elections.birth')} <input type="date" value={cand.birth_date} onChange={x => setCand({ ...cand, birth_date: x.target.value })} /></label>
                      <label>{t('elections.hire')} <input type="date" value={cand.hire_date} onChange={x => setCand({ ...cand, hire_date: x.target.value })} /></label>
                    </div>
                    <label style={{ fontSize: '.78rem', display: 'flex', gap: 6, alignItems: 'center' }}>
                      <input type="checkbox" checked={cand.declared} onChange={x => setCand({ ...cand, declared: x.target.checked })} />
                      {t('elections.honor_declaration')}
                    </label>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button type="submit" className="btn btn-primary" style={{ fontSize: '.78rem', padding: '4px 10px' }}>{t('elections.add_candidate')}</button>
                      <button type="button" className="btn" style={{ fontSize: '.78rem', padding: '4px 10px', background: 'var(--gray-300)' }} onClick={() => setCandFor(null)}>{t('organigramme.cancel')}</button>
                    </div>
                  </form>
                ) : (
                  <button className="btn" style={{ ...btnStyle, background: 'var(--blue)', color: '#fff' }} onClick={() => { setCandFor(e.id); setErr(null) }}>+ {t('elections.add_candidate')}</button>
                )}
              </div>
            )}

            {/* Vote */}
            {e.status === 'voting' && !e.has_voted && (
              <div style={{ marginTop: 10, borderTop: '1px solid var(--gray-200)', paddingTop: 10 }}>
                <p style={{ fontWeight: 600, fontSize: '.9rem' }}>🗳️ {t('elections.vote_prompt')}</p>
                {e.candidates.map(c => (
                  <label key={c.id} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '4px 0', fontSize: '.85rem' }}>
                    <input type="radio" name={`vote-${e.id}`} checked={voteFor === e.id && voteChoice === c.id} onChange={() => { setVoteFor(e.id); setVoteChoice(c.id) }} />
                    <strong>{c.full_name}</strong> — {c.list_label}
                  </label>
                ))}
                <button className="btn btn-primary" style={{ fontSize: '.8rem', marginTop: 6 }} disabled={voteFor !== e.id} onClick={() => vote(e.id)}>
                  {t('elections.vote_btn')}
                </button>
              </div>
            )}
            {e.status === 'voting' && e.has_voted && (
              <p style={{ color: 'var(--green)', fontSize: '.85rem', marginTop: 8 }}>✅ {t('elections.voted')}</p>
            )}

            {/* Résultats */}
            {resultsFor === e.id && results && (
              <div style={{ marginTop: 10, borderTop: '2px solid var(--blue)', paddingTop: 10 }}>
                <h4 style={{ margin: '0 0 6px' }}>📊 {t('elections.results')}</h4>
                <p style={{ fontSize: '.8rem', color: 'var(--gray-600)' }}>
                  {results.proportional ? t('elections.proportional') : t('elections.majority')} · {t('elections.turnout')}: {results.total_votes}/{results.voters_count}
                </p>
                {results.lists.map(l => (
                  <div key={l.list_label} style={{ marginBottom: 8 }}>
                    <strong style={{ fontSize: '.85rem' }}>{l.list_label}</strong> — {l.votes} {t('elections.votes')} ({l.seats_titulaires} {t('elections.titulaires').toLowerCase()} + {l.seats_suppleants} {t('elections.suppleants').toLowerCase()})
                    <div style={{ fontSize: '.82rem', marginLeft: 12 }}>
                      {l.elected.length > 0 && <div>✅ {t('elections.elected')}: {l.elected.join(', ')}</div>}
                      {l.suppleants.length > 0 && <div>🔁 {t('elections.suppleants')}: {l.suppleants.join(', ')}</div>}
                    </div>
                  </div>
                ))}
                <p style={{ fontSize: '.75rem', color: 'var(--gray-600)', marginTop: 8 }}>
                  📅 {t('elections.constituante_hint')} (L.416-1)
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  )
}

const btnStyle: React.CSSProperties = {
  fontSize: '.75rem', padding: '4px 10px', border: 'none', borderRadius: 4, cursor: 'pointer',
}
