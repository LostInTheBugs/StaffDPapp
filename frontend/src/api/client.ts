const API_BASE = '/api'

interface UserResponse {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  avatar_url: string | null
  language: string
  delegue_status: string
  delegue_role: string
  role: string
  totp_enabled: boolean
  is_delegue_securite_sante: boolean
  is_delegue_egalite: boolean
}

interface OrganizationResponse {
  id: number
  name: string
  slug: string
  company_name: string | null
  country: string
  employee_count: number
  mandate_end_date: string | null
  required_titulaires: number
  weekly_credit_hours: number | null
  enabled_modules: string[]
  logo_data: string | null
  contact_email: string | null
  contact_phone: string | null
  contact_hours: string | null
}

interface DashboardResponse {
  user: UserResponse
  organization: OrganizationResponse
}

interface InvitationResponse {
  id: number
  email: string
  first_name: string
  last_name: string
  delegue_status: string
  delegue_role: string
  is_delegue_securite_sante: boolean
  is_delegue_egalite: boolean
  is_used: boolean
  created_at: string | null
  organization_name: string | null
}

interface CreateInvitationResponse extends InvitationResponse {
  code: string  // plaintext, 26 chars Crockford base32 — shown ONLY once at creation
}

export type { InvitationResponse }

interface TokenResponse {
  access_token: string
  token_type: string
  mfa_required?: boolean
  mfa_token?: string | null
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${url}`, { ...options, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Erreur ${res.status}`)
  }
  return res.json()
}

export function login(email: string, password: string, captcha_id: string, captcha_answer: string): Promise<TokenResponse> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password, captcha_id, captcha_answer }) })
}

export function joinOrganization(data: {
  email: string; password: string; first_name: string; last_name: string; invitation_code: string
  captcha_id: string; captcha_answer: string
  vault_envelope?: VaultEnvelope | null
}): Promise<TokenResponse> {
  return request('/join', { method: 'POST', body: JSON.stringify(data) })
}

export function createOrganization(data: {
  organization_name: string; company_name?: string; employee_count: number
  admin_email: string; admin_password: string; admin_first_name: string; admin_last_name: string
  admin_delegue_status?: string; admin_delegue_role?: string
  captcha_id: string; captcha_answer: string
}): Promise<TokenResponse> {
  return request('/organizations', { method: 'POST', body: JSON.stringify(data) })
}

export function getDashboard(): Promise<DashboardResponse> {
  return request('/dashboard')
}

export function mfaLogin(mfa_token: string, totp_code: string): Promise<TokenResponse> {
  return request('/auth/mfa/login', { method: 'POST', body: JSON.stringify({ mfa_token, totp_code }) })
}

export function createInvitation(data: {
  email: string; first_name: string; last_name: string
  delegue_status: string; delegue_role: string
  is_delegue_securite_sante?: boolean; is_delegue_egalite?: boolean
  vault_envelope?: VaultEnvelope | null
}): Promise<CreateInvitationResponse> {
  return request('/invitations', { method: 'POST', body: JSON.stringify(data) })
}

export function listInvitations(): Promise<InvitationResponse[]> {
  return request('/invitations')
}

export interface BatchInviteResultItem {
  email: string
  first_name?: string | null
  last_name?: string | null
  status: 'created' | 'duplicate' | 'invalid'
  message?: string | null
  invitation?: (CreateInvitationResponse) | null
}

export interface BatchInviteResponse {
  results: BatchInviteResultItem[]
  created: number
  skipped: number
  failed: number
}

export function createInvitationsBatch(
  invitations: { email: string; first_name: string; last_name: string }[],
): Promise<BatchInviteResponse> {
  return request('/invitations/batch', { method: 'POST', body: JSON.stringify({ invitations }) })
}

export function removeMember(userId: number): Promise<{ id: number; removed: boolean }> {
  return request(`/organization/members/${userId}`, { method: 'DELETE' })
}

export interface NoticePost {
  id: number
  title: string
  body: string
  pinned: boolean
  created_by_id: number
  created_by_name: string | null
  created_at: string | null
  updated_at: string | null
}

export function listNotices(): Promise<NoticePost[]> {
  return request('/notices')
}

export function createNotice(data: { title: string; body: string; pinned?: boolean }): Promise<NoticePost> {
  return request('/notices', { method: 'POST', body: JSON.stringify(data) })
}

export function updateNotice(id: number, data: { title?: string; body?: string; pinned?: boolean }): Promise<NoticePost> {
  return request(`/notices/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteNotice(id: number): Promise<void> {
  return request(`/notices/${id}`, { method: 'DELETE' })
}

export interface ComplianceItem {
  key: string
  title: string
  legal_ref: string
  status: 'ok' | 'warn' | 'due' | 'na' | 'info'
  detail: string
}

export interface ComplianceEvent {
  id: number
  event_type: string
  event_date: string | null
  notes: string | null
  created_by_name: string | null
  created_at: string | null
}

export interface ComplianceOverview {
  items: ComplianceItem[]
  events: ComplianceEvent[]
  generated_at: string
}

export function getComplianceOverview(): Promise<ComplianceOverview> {
  return request('/compliance/overview')
}

export function createComplianceEvent(data: { event_type: string; event_date?: string; notes?: string }): Promise<ComplianceEvent> {
  return request('/compliance/events', { method: 'POST', body: JSON.stringify(data) })
}

export function deleteComplianceEvent(id: number): Promise<void> {
  return request(`/compliance/events/${id}`, { method: 'DELETE' })
}

export interface ElectionCandidate {
  id: number
  user_id: number | null
  full_name: string
  list_label: string
  eligible: boolean
  eligibility_reason: string | null
}

export interface Election {
  id: number
  title: string
  election_date: string | null
  candidate_deadline: string | null
  status: 'announced' | 'voting' | 'closed'
  notes: string | null
  candidates: ElectionCandidate[]
  votes_count: number
  has_voted: boolean
  can_manage: boolean
  created_by_name: string | null
}

export interface ElectionResultList {
  list_label: string
  votes: number
  seats_titulaires: number
  seats_suppleants: number
  elected: string[]
  suppleants: string[]
}

export interface ElectionResults {
  election_id: number
  status: string
  total_votes: number
  voters_count: number
  seats: number
  proportional: boolean
  lists: ElectionResultList[]
}

export function listElections(): Promise<Election[]> {
  return request('/elections')
}

export function createElection(data: { title: string; election_date: string; candidate_deadline?: string; notes?: string }): Promise<Election> {
  return request('/elections', { method: 'POST', body: JSON.stringify(data) })
}

export function addCandidate(electionId: number, data: {
  user_id?: number | null; full_name: string; list_label: string;
  birth_date?: string; hire_date?: string; declared_not_excluded?: boolean;
}): Promise<ElectionCandidate> {
  return request(`/elections/${electionId}/candidates`, { method: 'POST', body: JSON.stringify(data) })
}

export function removeCandidate(electionId: number, candidateId: number): Promise<void> {
  return request(`/elections/${electionId}/candidates/${candidateId}`, { method: 'DELETE' })
}

export function openElection(electionId: number): Promise<Election> {
  return request(`/elections/${electionId}/open`, { method: 'POST' })
}

export function castVote(electionId: number, candidateId: number): Promise<{ ok: boolean }> {
  return request(`/elections/${electionId}/vote`, { method: 'POST', body: JSON.stringify({ candidate_id: candidateId }) })
}

export function closeElection(electionId: number): Promise<ElectionResults> {
  return request(`/elections/${electionId}/close`, { method: 'POST' })
}

export function getElectionResults(electionId: number): Promise<ElectionResults> {
  return request(`/elections/${electionId}/results`)
}

export interface FormationMember {
  user_id: number
  full_name: string
  delegue_status: string
  is_first_mandate: boolean
  entitlement_hours: number
  used_hours: number
  remaining_hours: number
}

export interface FormationOverview {
  year: number
  members: FormationMember[]
}

export function getFormationOverview(): Promise<FormationOverview> {
  return request('/formation/overview')
}

export function setFirstMandate(userId: number, isFirstMandate: boolean): Promise<{ is_first_mandate: boolean }> {
  return request(`/formation/primo/${userId}`, { method: 'PUT', body: JSON.stringify({ is_first_mandate: isFirstMandate }) })
}

export interface SafetyRegisterEntry {
  id: number
  entry_date: string
  location: string
  description: string
  status: 'pending' | 'countersigned'
  chef_service_name: string
  countersigned_at: string | null
  delegate_name: string
  created_by_name: string
  can_countersign: boolean
  can_delete: boolean
}

export function listSafetyRegister(): Promise<SafetyRegisterEntry[]> {
  return request('/safety-register')
}

export function createSafetyRegisterEntry(data: { entry_date: string; location: string; description: string }): Promise<{ id: number }> {
  return request('/safety-register', { method: 'POST', body: JSON.stringify(data) })
}

export function countersignEntry(entryId: number, chefServiceName: string): Promise<{ status: string }> {
  return request(`/safety-register/${entryId}/countersign`, { method: 'POST', body: JSON.stringify({ chef_service_name: chefServiceName }) })
}

export function deleteSafetyRegisterEntry(entryId: number): Promise<void> {
  return request(`/safety-register/${entryId}`, { method: 'DELETE' })
}

export interface ProtectionPerson {
  kind: 'member' | 'candidate'
  name: string
  role: string
  election?: string
  protected_until: string | null
  days_left: number | null
  status: 'protected' | 'expired' | 'unknown'
}

export function getProtection(): Promise<{ today: string; people: ProtectionPerson[] }> {
  return request('/protection')
}

export function updateOrganization(data: {
  name?: string; company_name?: string; employee_count?: number; mandate_end_date?: string
  contact_email?: string; contact_phone?: string; contact_hours?: string
}): Promise<OrganizationResponse> {
  return request('/organization', { method: 'PUT', body: JSON.stringify(data) })
}

export function updateModules(modules: string[]): Promise<OrganizationResponse> {
  return request('/organization/modules', { method: 'PUT', body: JSON.stringify({ modules }) })
}

export function updateLogo(logo_data: string): Promise<OrganizationResponse> {
  return request('/organization/logo', { method: 'PUT', body: JSON.stringify({ logo_data }) })
}

export function deleteLogo(): Promise<OrganizationResponse> {
  return request('/organization/logo', { method: 'DELETE' })
}

export function getPublicOrg(slug: string): Promise<{ name: string; company_name: string | null; logo_data: string | null }> {
  return request(`/organizations/${encodeURIComponent(slug)}/public`)
}

export const ALL_MODULES = [
  'elections',
  'time_tracking',
  'notices',
  'compliance',
  'consultations',
  'workforce_stats',
  'delegate_activities',
  'legal',
  'contact',
] as const

export type ModuleName = typeof ALL_MODULES[number]

export const DELEGUE_STATUS = [
  { value: 'titulaire', label: 'Titulaire' },
  { value: 'suppleant', label: 'Suppléant(e)' },
  { value: 'employe', label: 'Salarié(e) non-élu(e)' },
] as const

export const DELEGUE_ROLES = [
  { value: 'president', label: 'Président(e)' },
  { value: 'vice_president', label: 'Vice-président(e)' },
  { value: 'secretaire', label: 'Secrétaire' },
  { value: 'membre', label: 'Membre du bureau' },
] as const

export const EMPLOYEE_RANGES = [
  { min: 15, max: 25, titulaires: 1 },
  { min: 26, max: 50, titulaires: 2 },
  { min: 51, max: 75, titulaires: 3 },
  { min: 76, max: 100, titulaires: 4 },
  { min: 101, max: 200, titulaires: 5 },
  { min: 201, max: 300, titulaires: 6 },
  { min: 301, max: 400, titulaires: 7 },
  { min: 401, max: 500, titulaires: 8 },
  { min: 501, max: 600, titulaires: 9 },
  { min: 601, max: 700, titulaires: 10 },
  { min: 701, max: 800, titulaires: 11 },
  { min: 801, max: 900, titulaires: 12 },
  { min: 901, max: 1000, titulaires: 13 },
  { min: 1001, max: 1100, titulaires: 14 },
  { min: 1101, max: 1500, titulaires: 15 },
  { min: 1501, max: 1900, titulaires: 16 },
  { min: 1901, max: 2300, titulaires: 17 },
  { min: 2301, max: 2700, titulaires: 18 },
  { min: 2701, max: 3100, titulaires: 19 },
  { min: 3101, max: 3500, titulaires: 20 },
  { min: 3501, max: 3900, titulaires: 21 },
  { min: 3901, max: 4300, titulaires: 22 },
  { min: 4301, max: 4700, titulaires: 23 },
  { min: 4701, max: 5100, titulaires: 24 },
  { min: 5101, max: 5500, titulaires: 25 },
] as const

interface Section {
  id: number | null
  position: number
  title: string
  visibility: string
  content: string  // base64
}

interface MinuteResponse {
  id: number
  meeting_id: number
  status: string
  is_encrypted: boolean
  created_by_id: number
  created_by_name: string | null
  validated_by_id: number | null
  validated_by_name: string | null
  validated_at: string | null
  created_at: string | null
  updated_at: string | null
  sections: Section[]
}

interface PreviewSection {
  position: number
  title: string
  content: string  // base64
}

interface DirectionPreview {
  minute_id: number
  meeting_title: string | null
  validated_by_name: string | null
  validated_at: string | null
  sections: PreviewSection[]
  generated_at: string
}

function b64Encode(str: string): string {
  return btoa(unescape(encodeURIComponent(str)))
}

function b64Decode(str: string): string {
  return decodeURIComponent(escape(atob(str)))
}

export function createMinute(meetingId: number, sections: Section[]): Promise<MinuteResponse> {
  const payload = {
    sections: sections.map(s => ({
      ...s,
      content: s.content ? b64Encode(s.content) : '',
    })),
  }
  return request(`/meetings/${meetingId}/minutes`, { method: 'POST', body: JSON.stringify(payload) })
}

export function getMeetingMinute(meetingId: number): Promise<MinuteResponse> {
  return request(`/meetings/${meetingId}/minute`)
}

export function getMinute(minuteId: number): Promise<MinuteResponse> {
  return request(`/minutes/${minuteId}`)
}

export function updateSections(minuteId: number, sections: Section[]): Promise<MinuteResponse> {
  const payload = {
    sections: sections.map(s => ({
      ...s,
      content: s.content ? b64Encode(s.content) : '',
    })),
  }
  return request(`/minutes/${minuteId}/sections`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function validateMinute(minuteId: number): Promise<{ status: string; message: string }> {
  return request(`/minutes/${minuteId}/validate`, { method: 'POST' })
}

export function getDirectionPreview(minuteId: number): Promise<DirectionPreview> {
  return request(`/minutes/${minuteId}/direction-preview`)
}

export interface PublishResult {
  status: string
  message: string
  publication_id: number
  sections_count: number
}

export function publishMinute(minuteId: number, pdfSha256: string): Promise<PublishResult> {
  return request(`/minutes/${minuteId}/publish`, {
    method: 'POST',
    body: JSON.stringify({ pdf_sha256: pdfSha256 }),
  })
}

// ── Vault API ────────────────────────────────────────────────────────

interface VaultStatusResponse {
  enabled: boolean
  has_key: boolean
  dek_version: number | null
  recovery_enabled?: boolean
}

interface VaultKeyResponse {
  wrapped_dek: string   // base64
  nonce: string         // base64
  kdf_salt: string      // base64
  kdf_params: string    // JSON
  dek_version: number
  recovery_enabled?: boolean
  // Enveloppe de récupération (présente seulement si recovery_enabled)
  recovery_wrapped_dek?: string
  recovery_nonce?: string
  recovery_kdf_salt?: string
  recovery_kdf_params?: string
}

interface RecoveryEnvelope {
  wrapped_dek: string   // base64
  nonce: string         // base64
  kdf_salt: string      // base64
  kdf_params: string    // JSON
}

interface VaultEnvelope {
  wrapped_dek: string   // base64
  nonce: string         // base64
  kdf_salt: string      // base64
  kdf_params: string    // JSON
}

export function createVault(envelope: VaultEnvelope): Promise<VaultKeyResponse> {
  return request('/vault', { method: 'POST', body: JSON.stringify(envelope) })
}

export function getVaultKey(): Promise<VaultKeyResponse> {
  return request('/vault/key')
}

export function replaceVaultKey(envelope: VaultEnvelope): Promise<VaultKeyResponse> {
  return request('/vault/key', { method: 'PUT', body: JSON.stringify(envelope) })
}

export function getVaultStatus(): Promise<VaultStatusResponse> {
  return request('/vault/status')
}

export function setVaultRecoveryKey(envelope: RecoveryEnvelope): Promise<VaultKeyResponse> {
  return request('/vault/recovery-key', { method: 'PUT', body: JSON.stringify(envelope) })
}

export function deleteVaultRecoveryKey(): Promise<VaultStatusResponse> {
  return request('/vault/recovery-key', { method: 'DELETE' })
}

export function attachInvitationEnvelope(invitationId: number, envelope: VaultEnvelope): Promise<VaultKeyResponse> {
  return request(`/invitations/${invitationId}/vault-envelope`, { method: 'POST', body: JSON.stringify(envelope) })
}

export function getJoinVaultEnvelope(code: string, email: string): Promise<VaultKeyResponse> {
  return request('/join/vault-envelope', { method: 'POST', body: JSON.stringify({ code, email }) })
}

// ── Consultations L.414-3 ──────────────────────────────────────────────
export interface Consultation {
  id: number
  title: string
  category: string
  description: string | null
  status: string
  requested_at: string | null
  response_due: string | null
  direction_responded_at: string | null
  direction_response: string | null
  created_by_name: string | null
}

export interface ConsultationStats {
  total: number
  pending: number
  overdue: number
  received: number
  closed: number
}

export function listConsultations(): Promise<Consultation[]> {
  return request('/consultations')
}

export function getConsultationStats(): Promise<ConsultationStats> {
  return request('/consultations/stats')
}

export function createConsultation(data: {
  title: string
  category: string
  description?: string
  response_due?: string
}): Promise<Consultation> {
  return request('/consultations', { method: 'POST', body: JSON.stringify(data) })
}

export function updateConsultation(
  id: number,
  data: { status?: string; direction_response?: string; description?: string; response_due?: string },
): Promise<Consultation> {
  return request(`/consultations/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}

export function deleteConsultation(id: number): Promise<void> {
  return request(`/consultations/${id}`, { method: 'DELETE' })
}

// ── Workforce statistics L.414-3 ───────────────────────────────────────

export interface WorkforceStat {
  id: number
  organization_id: number
  semester: string
  male_count: number
  female_count: number
  total: number
  created_at: string | null
}

export function listWorkforceStats(): Promise<WorkforceStat[]> {
  return request('/workforce-stats')
}

export function getLatestWorkforceStat(): Promise<WorkforceStat | null> {
  return request('/workforce-stats/latest')
}

export function createWorkforceStat(data: {
  semester: string
  male_count: number
  female_count: number
}): Promise<WorkforceStat> {
  return request('/workforce-stats', { method: 'POST', body: JSON.stringify(data) })
}

export function updateWorkforceStat(
  id: number,
  data: { male_count?: number; female_count?: number },
): Promise<WorkforceStat> {
  return request(`/workforce-stats/${id}`, { method: 'PUT', body: JSON.stringify(data) })
}

export function deleteWorkforceStat(id: number): Promise<void> {
  return request(`/workforce-stats/${id}`, { method: 'DELETE' })
}

// ── Rapport d'activité annuel ───────────────────────────────────────────

export interface AnnualReportDesignate {
  user_id: number
  name: string
  email: string
  delegue_status: string
  roles: string[]
  total_hours: number
  hours_by_category: Record<string, number>
  activities_count: number
  activities_by_category: Record<string, number>
}

export interface AnnualReportData {
  year: number
  organization: {
    name: string
    company: string | null
    employee_count: number
    weekly_credit_hours: number | null
    equality_monthly_credit: number
  }
  workforce: Array<{ semester: string; male_count: number; female_count: number; total: number }>
  hours: {
    total: number
    by_category: Record<string, number>
    by_user: Array<{ user_id: number; name: string; email: string; delegue_status: string; total_hours: number }>
  }
  meetings: { total: number; with_direction: number }
  consultations: { total: number; answered: number }
  designates: AnnualReportDesignate[]
}

export function getAnnualReport(year: number): Promise<AnnualReportData> {
  return request(`/stats/annual-report?year=${year}`)
}

export type { VaultStatusResponse, VaultKeyResponse, VaultEnvelope }

export { b64Encode, b64Decode }
export type { Section, MinuteResponse, DirectionPreview }
