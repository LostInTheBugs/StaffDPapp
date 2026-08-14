import { Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import JoinOrganization from './pages/JoinOrganization'
import CreateOrganization from './pages/CreateOrganization'
import Dashboard from './pages/Dashboard'
import EditOrganization from './pages/EditOrganization'
import AccountSettings from './pages/AccountSettings'
import Organigramme from './pages/Organigramme'
import Meetings from './pages/Meetings'
import TimeTracking from './pages/TimeTracking'
import MinutesPage from './pages/Minutes'
import MinutesArchive from './pages/MinutesArchive'
import DelegateActivities from './pages/DelegateActivities'
import Notifications from './pages/Notifications'
import ShareView from './pages/ShareView'
import Consultations from './pages/Consultations'
import WorkforceStats from './pages/WorkforceStats'
import ProtectedRoute from './components/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/join" element={<JoinOrganization />} />
      <Route path="/create" element={<CreateOrganization />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/organization" element={<ProtectedRoute><EditOrganization /></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><AccountSettings /></ProtectedRoute>} />
      <Route path="/organigramme" element={<ProtectedRoute><Organigramme /></ProtectedRoute>} />
      <Route path="/meetings" element={<ProtectedRoute><Meetings /></ProtectedRoute>} />
      <Route path="/hours" element={<ProtectedRoute><TimeTracking /></ProtectedRoute>} />
      <Route path="/meetings/:meetingId/minutes" element={<ProtectedRoute><MinutesPage /></ProtectedRoute>} />
      <Route path="/archive" element={<ProtectedRoute><MinutesArchive /></ProtectedRoute>} />
      <Route path="/delegate-activities" element={<ProtectedRoute><DelegateActivities /></ProtectedRoute>} />
      <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
      <Route path="/consultations" element={<ProtectedRoute><Consultations /></ProtectedRoute>} />
      <Route path="/workforce-stats" element={<ProtectedRoute><WorkforceStats /></ProtectedRoute>} />
      <Route path="/p/:token" element={<ShareView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
