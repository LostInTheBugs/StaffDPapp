const API_BASE = '/api'

interface TokenResponse {
  access_token: string
  token_type: string
}

interface UserResponse {
  id: number
  email: string
  full_name: string
  role: string
}

interface DashboardResponse {
  user: UserResponse
  organization: {
    id: number
    name: string
    slug: string
    company_name: string | null
    country: string
  }
}

interface InvitationResponse {
  code: string
  organization_name: string
}

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}${url}`, { ...options, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Erreur ${res.status}`)
  }
  return res.json()
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function joinOrganization(data: {
  email: string
  password: string
  full_name: string
  invitation_code: string
}): Promise<TokenResponse> {
  return request<TokenResponse>('/join', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function createOrganization(data: {
  organization_name: string
  company_name?: string
  admin_email: string
  admin_password: string
  admin_full_name: string
}): Promise<TokenResponse> {
  return request<TokenResponse>('/organizations', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getMe(): Promise<UserResponse> {
  return request<UserResponse>('/auth/me')
}

export function getDashboard(): Promise<DashboardResponse> {
  return request<DashboardResponse>('/dashboard')
}

export function createInvitation(): Promise<InvitationResponse> {
  return request<InvitationResponse>('/invitations', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

export function listInvitations(): Promise<InvitationResponse[]> {
  return request<InvitationResponse[]>('/invitations')
}
