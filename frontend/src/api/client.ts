import type {
  CitiesResponse,
  LoginResponse,
  MatchDTO,
  PathResult,
  PublicSearchDTO,
  UserProfile,
  AdminUserUpdateDTO,
} from './types'

function apiBase(): string {
  const raw = import.meta.env.VITE_API_URL
  const base =
    typeof raw === 'string' && raw.length > 0
      ? raw.replace(/\/$/, '')
      : 'http://localhost:8000'
  return base
}

export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${apiBase()}${p}`
}

function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          return String((item as { msg: unknown }).msg)
        }
        return JSON.stringify(item)
      })
      .join('; ')
  }
  return 'Request failed'
}

export async function readApiError(res: Response): Promise<string> {
  try {
    const data: unknown = await res.json()
    if (data && typeof data === 'object' && 'detail' in data) {
      return formatDetail((data as { detail: unknown }).detail)
    }
  } catch {
    /* ignore */
  }
  return res.statusText || 'Request failed'
}

// The backend sets the JWT as an httpOnly cookie on /login. We never read or
// store the token in JS — `credentials: 'include'` makes the browser attach
// the cookie automatically on every request below. This is what protects
// the token from theft via XSS.

export async function loginRequest(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)

  const res = await fetch(apiUrl('/login'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<LoginResponse>
}

export async function logoutRequest(): Promise<void> {
  const res = await fetch(apiUrl('/logout'), {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
}

export type RegisterBody = {
  email: string
  password: string
  full_name?: string
  first_name?: string
  last_name?: string
  phone?: string
}

export async function registerRequest(payload: RegisterBody): Promise<void> {
  const res = await fetch(apiUrl('/register'), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
}

export async function fetchCities(): Promise<CitiesResponse> {
  const res = await fetch(apiUrl('/cities'))
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<CitiesResponse>
}

export async function fetchPath(
  start: string,
  goal: string,
): Promise<PathResult> {
  const res = await fetch(apiUrl('/path'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ start, goal }),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<PathResult>
}

export async function saveSearch(payload: {
  start_city: string
  goal_city: string
  path: string[]
  distance: number
  is_public: boolean
  comment?: string
}): Promise<MatchDTO[]> {
  const res = await fetch(apiUrl('/search'), {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<MatchDTO[]>
}

export async function fetchPublicSearches(
  window: '1h' | '6h' | '1d',
): Promise<PublicSearchDTO[]> {
  const res = await fetch(apiUrl(`/public-searches?window=${window}`), {
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<PublicSearchDTO[]>
}

export async function fetchMe(): Promise<UserProfile> {
  const res = await fetch(apiUrl('/me'), {
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<UserProfile>
}

export async function updateMe(payload: {
  first_name?: string
  last_name?: string
  phone?: string
}): Promise<UserProfile> {
  const res = await fetch(apiUrl('/me'), {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<UserProfile>
}

export async function subscribe(): Promise<void> {
  const res = await fetch(apiUrl('/subscribe'), {
    method: 'POST',
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
}

export async function adminFetchUsers(): Promise<UserProfile[]> {
  const res = await fetch(apiUrl('/admin/users'), {
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<UserProfile[]>
}

export async function adminUpdateUser(
  id: number,
  payload: AdminUserUpdateDTO,
): Promise<UserProfile> {
  const res = await fetch(apiUrl(`/admin/users/${id}`), {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
  return res.json() as Promise<UserProfile>
}

export async function adminDeleteUser(id: number): Promise<void> {
  const res = await fetch(apiUrl(`/admin/users/${id}`), {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) {
    throw new Error(await readApiError(res))
  }
}