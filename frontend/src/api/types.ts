export type CityDTO = {
  name: string
  lat: number
  lon: number
}

export type CitiesResponse = Record<string, CityDTO>

export type UserProfile = {
  id: number
  email: string
  full_name: string
  first_name: string | null
  last_name: string | null
  phone: string | null
  is_pro: boolean
}

export type UserUpdateDTO = {
  first_name?: string
  last_name?: string
  phone?: string
}

export type LoginResponse = {
  access_token: string
  token_type: string
}

export type PathResult = {
  start: string
  goal: string
  path: string[]
  distance: number
  visited: string[]
}

export type MatchDTO = {
  user_full_name: string
  user_phone: string | null
  start_city: string
  goal_city: string
  path: string[]
  distance: number
  comment: string | null
  created_at: string
}

export type PublicSearchDTO = {
  id: number
  start_city: string
  goal_city: string
  path: string[]
  distance: number
  comment: string | null
  created_at: string
  user_first_name: string | null
  user_last_name: string | null
  user_phone: string | null
}
