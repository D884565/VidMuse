import { Navigate } from 'react-router-dom'
import useAuthStore from '@/store/authStore'

function AuthGuard({ children }) {
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn)

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />
  }

  return children
}

export default AuthGuard
