import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Container } from './styles'
import { Sidebar, TopBar, MainContent } from './components/ui/Layout'
import { useDispatch } from 'react-redux'
import { setStatus } from './store/systemReducer'

import { Overview } from './pages/Overview'
import { AnalyzePCAP } from './pages/AnalyzePCAP'
import { NetworkState } from './pages/NetworkState'
import { Forecast } from './pages/Forecast'
import { Mitre } from './pages/Mitre'
import { Explainability } from './pages/Explainability'
import { AttackGraph } from './pages/AttackGraph'
import { CounterfactualLab } from './pages/CounterfactualLab'
import { ModelTestCenter } from './pages/ModelTestCenter'
import { Evaluation } from './pages/Evaluation'
import { Scenarios } from './pages/Scenarios'
import { System } from './pages/System'
import { History } from './pages/History'
import { ReportExport } from './pages/ReportExport'

const navLinks = [
  { path: '/', label: 'Overview', exact: true },
  { path: '/analyze', label: 'Analyze PCAP' },
  { path: '/network-state', label: 'Network State' },
  { path: '/forecast', label: 'Attack Forecast' },
  { path: '/mitre', label: 'MITRE ATT&CK' },
  { path: '/explainability', label: 'Explainability' },
  { path: '/attack-graph', label: 'Attack Graph' },
  { path: '/counterfactual', label: 'Counterfactual Lab' },
  { path: '/model-test', label: 'Model Test Center' },
  { path: '/evaluation', label: 'Evaluation' },
  { path: '/scenarios', label: 'Scenarios' },
  { path: '/system', label: 'System' },
  { path: '/history', label: 'Analysis History' },
  { path: '/report', label: 'Export Report' },
]

function App() {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [status, setStatusLocal] = useState({
    backend: 'Disconnected',
    worldModel: 'Uninitialized',
    data: 'No Analysis',
  })
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    fetch('/api/models/status')
      .then(res => res.json())
      .then(data => {
        setStatusLocal({
          backend: data.backend || 'Disconnected',
          worldModel: data.world_model || 'Uninitialized',
          data: data.active_traffic?.filename || 'No Analysis',
        })
      })
      .catch(() => setStatusLocal({ backend: 'Disconnected', worldModel: 'Error', data: 'No Analysis' }))
  }, [])

  const toggleCollapse = () => setIsCollapsed(prev => !prev)

  return (
    <Router>
      <Container>
        <Sidebar
          navLinks={navLinks}
          onLinkClick={() => setIsCollapsed(prev => !prev)}
          isCollapsed={isCollapsed}
          toggleCollapse={toggleCollapse}
        />
        <TopBar
          title="Cyber World Model"
          subtitle="AI-Powered Network Attack Forecasting & Proactive Defence"
        />
        <MainContent pageTitle={navLinks.find(l => l.path === location.pathname)?.label || 'Overview'}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/analyze" element={<AnalyzePCAP />} />
            <Route path="/network-state" element={<NetworkState />} />
            <Route path="/forecast" element={<Forecast />} />
            <Route path="/mitre" element={<Mitre />} />
            <Route path="/explainability" element={<Explainability />} />
            <Route path="/attack-graph" element={<AttackGraph />} />
            <Route path="/counterfactual" element={<CounterfactualLab />} />
            <Route path="/model-test" element={<ModelTestCenter />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/scenarios" element={<Scenarios />} />
            <Route path="/system" element={<System />} />
            <Route path="/history" element={<History />} />
            <Route path="/report" element={<ReportExport />} />
            <Route path="*" element={<Overview />} />
          </Routes>
        </MainContent>
      </Container>
    </Router>
  )
}

export default App