import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Jobs from './pages/Jobs'
import JobDetail from './pages/JobDetail'
import Configs from './pages/Configs'
import Logs from './pages/Logs'
import CVProfile from './pages/CVProfile'
import VoiceProfile from './pages/VoiceProfile'
import JobMatching from './pages/JobMatching'
import Documents from './pages/Documents'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="jobs/:id" element={<JobDetail />} />
        <Route path="configs" element={<Configs />} />
        <Route path="logs" element={<Logs />} />
        <Route path="cv" element={<CVProfile />} />
        <Route path="voice" element={<VoiceProfile />} />
        <Route path="matching" element={<JobMatching />} />
        <Route path="documents" element={<Documents />} />
      </Route>
    </Routes>
  )
}

export default App
