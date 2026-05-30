import axios from 'axios'
import { useRouter } from 'vue-router'

export function useAuth() {
  const router = useRouter()

  const token = () => localStorage.getItem('token') ?? ''
  const headers = () => ({ Authorization: `Bearer ${token()}` })
  const logout = () => {
    localStorage.removeItem('token')
    router.push('/login')
  }

  axios.interceptors.response.use(
    res => res,
    err => {
      if (err.response?.status === 401) logout()
      return Promise.reject(err)
    }
  )

  return { token, headers, logout }
}
