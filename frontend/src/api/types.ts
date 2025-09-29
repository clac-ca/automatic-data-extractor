export interface UserProfile {
  user_id: string
  email: string
  role: string
  is_active: boolean
}

export interface SessionEnvelope {
  user: UserProfile
  expires_at: string
  refresh_expires_at: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface InitialSetupStatus {
  initialSetupRequired: boolean
}

export interface InitialSetupPayload {
  email: string
  password: string
  displayName?: string | null
}
