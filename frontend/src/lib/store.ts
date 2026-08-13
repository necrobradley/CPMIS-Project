import { create } from 'zustand'
import Cookies from 'js-cookie'
import { authApi } from '@/lib/api'

export type UserRole = 'owner' | 'admin' | 'director' | 'manager' | 'staff' | 'subcontractor'

export interface User {
  id: number
  name: string
  email?: string
  role: UserRole
  phone?: string
  division_id?: number
  telegram_id?: string
  avatar_url?: string
  is_active: boolean
  email_verified_at?: string
  email_verification_required?: boolean
  must_set_password?: boolean
  created_at: string
}

interface AuthState {
  user:    User | null
  loading: boolean
  setUser: (user: User | null) => void
  login:   (email: string, password: string) => Promise<void>
  logout:  () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user:    null,
  loading: true,

  setUser: (user) => set({ user }),

  login: async (email, password) => {
    const { data } = await authApi.login(email, password)
    Cookies.set('access_token',  data.access_token,  { expires: 1 })
    Cookies.set('refresh_token', data.refresh_token, { expires: 7 })
    const me = await authApi.me()
    set({ user: me.data })
  },

  logout: () => {
    Cookies.remove('access_token')
    Cookies.remove('refresh_token')
    set({ user: null })
    window.location.href = '/login'
  },

  fetchMe: async () => {
    try {
      const token = Cookies.get('access_token')
      if (!token) { set({ loading: false }); return }
      const { data } = await authApi.me()
      set({ user: data, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },
}))
