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
import NoticeBoard from './pages/NoticeBoard'
import ComplianceBoard from './pages/ComplianceBoard'
import Elections from './pages/Elections'
import { FormationPage, SafetyRegisterPage, ProtectionPage } from './pages/LegalPages'
import Notifications from './pages/Notifications'
import ShareView from './pages/ShareView'
import Consultations from './pages/Consultations'
import WorkforceStats from './pages/WorkforceStats'
import ContactPage from './pages/ContactPage'
import ProtectedRoute from './components/ProtectedRoute'
import ModuleRoute from './components/ModuleRoute'

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
      <Route path="/hours" element={<ModuleRoute module="time_tracking"><TimeTracking /></ModuleRoute>} />
      <Route path="/meetings/:meetingId/minutes" element={<ProtectedRoute><MinutesPage /></ProtectedRoute>} />
      <Route path="/archive" element={<ProtectedRoute><MinutesArchive /></ProtectedRoute>} />
      <Route path="/delegate-activities" element={<ModuleRoute module="delegate_activities"><DelegateActivities /></ModuleRoute>} />
      <Route path="/notices" element={<ModuleRoute module="notices"><NoticeBoard /></ModuleRoute>} />
      <Route path="/compliance" element={<ModuleRoute module="compliance"><ComplianceBoard /></ModuleRoute>} />
      <Route path="/elections" element={<ModuleRoute module="elections"><Elections /></ModuleRoute>} />
      <Route path="/formation" element={<ModuleRoute module="legal"><FormationPage /></ModuleRoute>} />
      <Route path="/safety-register" element={<ModuleRoute module="legal"><SafetyRegisterPage /></ModuleRoute>} />
      <Route path="/protection" element={<ModuleRoute module="legal"><ProtectionPage /></ModuleRoute>} />
      <Route path="/notifications" element={<ProtectedRoute><Notifications /></ProtectedRoute>} />
      <Route path="/consultations" element={<ModuleRoute module="consultations"><Consultations /></ModuleRoute>} />
      <Route path="/workforce-stats" element={<ModuleRoute module="workforce_stats"><WorkforceStats /></ModuleRoute>} />
      <Route path="/contact" element={<ModuleRoute module="contact"><ContactPage /></ModuleRoute>} />
      <Route path="/p/:token" element={<ShareView />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
