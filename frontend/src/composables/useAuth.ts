import { useRouter } from 'vue-router'

export function useAuth() {
  const router = useRouter()

  const token = () => localStorage.getItem('token') ?? ''
  const headers = () => ({ Authorization: `Bearer ${token()}` })
  const logout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  // Interceptor wird einmalig in main.ts registriert, nicht hier
  return { token, headers, logout }
}
