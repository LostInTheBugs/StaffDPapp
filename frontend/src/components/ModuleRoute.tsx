import { Navigate } from 'react-router-dom'
import { useAuth, hasModule } from '../hooks/useAuth'
import type { ReactNode } from 'react'

/**
 * Route protégée + garde de module : si le module est désactivé pour
 * l'organisation, redirige vers le dashboard (le backend renvoie aussi 403).
 */
export default function ModuleRoute({ module, children }: { module: string; children: ReactNode }) {
  const { token, organization } = useAuth()

  if (!token) return <Navigate to="/login" replace />
  if (!hasModule(organization, module)) return <Navigate to="/dashboard" replace />

  return <>{children}</>
}
