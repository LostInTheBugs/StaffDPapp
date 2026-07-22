const API_BASE = '/api'

interface UserResponse {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  delegue_status: string
  delegue_role: string
  role: string
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
  required_titulaires: number
}

interface DashboardResponse {
  user: UserResponse
  organization: OrganizationResponse
}

interface InvitationResponse {
  code: string
  email: string
  first_name: string
  last_name: string
  delegue_status: string
  delegue_role: string
  is_delegue_securite_sante: boolean
  is_delegue_egalite: boolean
  organization_name: string | null
}

export type { InvitationResponse }

interface TokenResponse {
  access_token: string
  token_type: string
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

export function login(email: string, password: string): Promise<TokenResponse> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function joinOrganization(data: {
  email: string; password: string; first_name: string; last_name: string; invitation_code: string
}): Promise<TokenResponse> {
  return request('/join', { method: 'POST', body: JSON.stringify(data) })
}

export function createOrganization(data: {
  organization_name: string; company_name?: string; employee_count: number
  admin_email: string; admin_password: string; admin_first_name: string; admin_last_name: string
}): Promise<TokenResponse> {
  return request('/organizations', { method: 'POST', body: JSON.stringify(data) })
}

export function getDashboard(): Promise<DashboardResponse> {
  return request('/dashboard')
}

export function createInvitation(data: {
  email: string; first_name: string; last_name: string
  delegue_status: string; delegue_role: string
  is_delegue_securite_sante?: boolean; is_delegue_egalite?: boolean
}): Promise<InvitationResponse> {
  return request('/invitations', { method: 'POST', body: JSON.stringify(data) })
}

export function listInvitations(): Promise<InvitationResponse[]> {
  return request('/invitations')
}

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
