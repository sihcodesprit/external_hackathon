export const Container = ({ children }: any) => {
  return (
    <div style={{
      maxWidth: '1400px',
      margin: '0 auto',
      padding: '0 2rem',
    }}>
      {children}
    </div>
  )
}

const globalStyles = `
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  
  body {
    font-family: 'Inter', 'SF Pro Display', 'Segoe UI', system-ui, sans-serif;
    background-color: #0a0e17;
    color: #e8eef5;
    min-height: 100vh;
    line-height: 1.6;
  }
  
  a {
    text-decoration: none;
    color: inherit;
  }
  
  button {
    cursor: pointer;
    border: none;
    font-family: inherit;
  }
  
  .sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: 260px;
    background: #111827;
    transition: width 0.3s ease;
    z-index: 100;
  }
  
  .sidebar.collapsed {
    width: 80px;
  }
  
  .sidebar-header {
    padding: 1.5rem;
    border-bottom: 1px solid #2a344f;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  
  .logo {
    font-size: 1.25rem;
    font-weight: 600;
    color: #00d4aa;
  }
  
  .nav-links {
    list-style: none;
    padding: 0.5rem 0;
  }
  
  .nav-item {
    padding: 0.5rem 1rem;
  }
  
  .nav-link {
    color: #7d8a9e;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: 100%;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    transition: background 0.2s;
  }
  
  .nav-link:hover {
    background: #1a2232;
    color: #00d4aa;
  }
  
  .nav-item.active .nav-link {
    background: #00d4aa;
    color: #0a0e17;
  }
  
  .bottom-section {
    padding: 1rem 1rem 0;
    border-top: 1px solid #2a344f;
    margin-top: 1rem;
  }
  
  .system-status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #7d8a9e;
    font-size: 0.875rem;
  }
  
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  
  .status-connected { background: #48bb78; }
  .status-disconnected { background: #ff5a5f; }
  
  .top-bar {
    background: #111827;
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #2a344f;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .top-bar-left h1 {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 600;
  }
  
  .top-bar-left p {
    margin: 0.25rem 0 0;
    color: #7d8a9e;
    font-size: 0.875rem;
  }
  
  .status-panel {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: #7d8a9e;
    font-size: 0.875rem;
  }
  
  .refresh-btn {
    background: transparent;
    border: 1px solid #2a344f;
    color: #7d8a9e;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    transition: all 0.2s;
  }
  
  .refresh-btn:hover {
    background: #2a344f;
    color: #00d4aa;
  }
  
  .main-content {
    margin-left: 260px;
    transition: margin-left 0.3s ease;
    min-height: 100vh;
  }
  
  .main-content.collapsed {
    margin-left: 80px;
  }
  
  .page-header h2 {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }
  
  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }
  
  .hero-section {
    text-align: center;
    padding: 3rem 2rem;
  }
  
  .hero-section h1 {
    font-size: 2.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-bottom: 1rem;
  }
  
  .hero-section p {
    color: #7d8a9e;
    font-size: 1.125rem;
    line-height: 1.6;
    max-width: 600px;
    margin: 0 auto;
  }
  
  .metric-card {
    background: #1a2232;
    border: 1px solid #2a344f;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
    transition: all 0.2s;
  }
  
  .metric-card:hover {
    border-color: #00d4aa;
  }
  
  .metric-card h3 {
    color: #7d8a9e;
    font-size: 0.875rem;
    margin-bottom: 0.5rem;
  }
  
  .metric-card .value {
    color: #e8eef5;
    font-size: 2rem;
    font-weight: 600;
  }
  
  .metric-card .subtitle {
    color: #5a6a7e;
    font-size: 0.75rem;
  }
  
  .card {
    background: #1a2232;
    border: 1px solid #2a344f;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1rem;
  }
  
  .card h3 {
    color: #7d8a9e;
    font-size: 0.875rem;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #2a344f;
  }
  
  .alert-low { background: rgba(72, 187, 120, 0.1); border-color: #48bb78; }
  .alert-elevated { background: rgba(246, 193, 65, 0.1); border-color: #f6c141; }
  .alert-high { background: rgba(255, 90, 95, 0.1); border-color: #ff5a5f; }
  .alert-critical { background: rgba(255, 46, 99, 0.1); border-color: #ff2e63; }
  
  .bg-low { background: #48bb78; color: #0a0e17; }
  .bg-cyan { background: #00b4d8; color: #0a0e17; }
  .bg-orange { background: #ff6b35; color: #0a0e17; }
  .bg-blue { background: #00d4aa; color: #0a0e17; }
`

import { createGlobalStyle } from 'styled-components'

export const GlobalStyle = createGlobalStyle`${globalStyles}`