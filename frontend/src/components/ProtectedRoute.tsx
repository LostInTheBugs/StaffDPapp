import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useVault } from '../hooks/useVault'
import VaultUnlock from './VaultUnlock'
import type { ReactNode } from 'react'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  const { status } = useVault()

  if (!token) return <Navigate to="/login" replace />

  // If vault is locked, show the unlock overlay on top of everything
  if (status === 'locked') {
    return (
      <>
        {children}
        <VaultUnlock />
      </>
    )
  }

  return <>{children}</>
}
