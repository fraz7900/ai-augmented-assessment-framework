import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { ClipboardList, ShieldCheck, Upload } from 'lucide-react'
import AssessmentsListPage from './routes/AssessmentsListPage'
import UploadPage from './routes/UploadPage'
import AssessmentDetailPage from './routes/AssessmentDetailPage'
import OverviewTab from './routes/tabs/OverviewTab'
import EvidenceTab from './routes/tabs/EvidenceTab'
import DashboardTab from './routes/tabs/DashboardTab'
import ChatTab from './routes/tabs/ChatTab'
import OrganizationSelect from './components/OrganizationSelect'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
  }`

function App() {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
          <span className="inline-flex items-center gap-2 font-semibold text-slate-900">
            <ShieldCheck className="h-5 w-5 text-slate-700" aria-hidden="true" />
            Compliance Assessment Platform
          </span>
          <nav className="flex gap-2">
            <NavLink to="/" end className={navLinkClass}>
              <span className="inline-flex items-center gap-1.5">
                <ClipboardList className="h-4 w-4" aria-hidden="true" />
                Assessments
              </span>
            </NavLink>
            <NavLink to="/upload" className={navLinkClass}>
              <span className="inline-flex items-center gap-1.5">
                <Upload className="h-4 w-4" aria-hidden="true" />
                Upload
              </span>
            </NavLink>
          </nav>
          <OrganizationSelect />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<AssessmentsListPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/assessments/:assessmentId" element={<AssessmentDetailPage />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewTab />} />
            <Route path="evidence" element={<EvidenceTab />} />
            <Route path="dashboard" element={<DashboardTab />} />
            <Route path="chat" element={<ChatTab />} />
          </Route>
        </Routes>
      </main>
    </div>
  )
}

export default App
