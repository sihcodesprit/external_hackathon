import React, { useState, useEffect, useRef } from 'react'
import { Container } from './styles'
import { NavLink } from 'react-router-dom'
import { colors, typography, spacing, radius, shadow } from './styles/designSystem'

const sidebarWidth = 260
const collapsedWidth = 80

export const Sidebar = ({ navLinks, onLinkClick, isCollapsed, toggleCollapse }: any) => {
  return (
    <nav className="sidebar" style={{ width: isCollapsed ? collapsedWidth : sidebarWidth }}>
      <div className="sidebar-header">
        <span className="logo">
          <span>CYBER</span>
          <span>WORLD MODEL</span>
        </span>
        <button
          className="toggle-btn"
          onClick={toggleCollapse}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? '⇧' : '≡'}
        </button>
      </div>
      <ul className="nav-links">
        {navLinks.map((link: any) => (
          <li key={link.path} className={({
            active: isActive,
          } => `nav-item ${isActive && 'active'}(`)(link.path === window.location.pathname || (link.path === '/' && !window.location.pathname.includes('/')))}`}
          >
            <NavLink
              to={link.path}
              exact={link.exact}
              className="nav-link"
              style={{
                color: isActive ? colors.accent_blue : colors.text_primary,
                fontWeight: isActive ? 500 : 400,
              }}
            >
              {link.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="bottom-section">
        <div className="system-status">
          <span className="dot status-connected"></span>
          Backend Connected
        </div>
        <button
          className="logout-btn"
          onClick={() => window.location.href = '/'}
          style={{
            marginTop: spacing.sm,
            width: '100%',
            padding: `${spacing.sm} ${spacing.md}`,
            background: 'transparent',
            border: `1px solid ${colors.border}`,
            color: colors.text_secondary,
            fontSize: typography.fontSize.sm,
            borderRadius: radius.md,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          Logout
        </button>
      </div>
    </nav>
  )
}

export const TopBar = ({ title, subtitle }: any) => {
  return (
    <header className="top-bar" style={{ background: colors.surface, padding: `${spacing.md} ${spacing.lg}` }}>
      <div className="top-bar-left">
        <h1 style={{ color: colors.text_primary, fontSize: typography.fontSize['3xl'], fontWeight: 600 }}>{title}</h1>
        <p style={{ color: colors.text_secondary, marginTop: spacing.xs, fontSize: typography.fontSize.sm }}>{subtitle}</p>
      </div>
      <div className="top-bar-right">
        <div className="status-panel">
          <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>Model:</span>
          <span style={{ color: colors.accent_blue, fontWeight: 500, marginLeft: spacing.xs }}>{'LSTM World Model'}</span>
        </div>
        <div className="status-panel">
          <span style={{ color: colors.text_muted, fontSize: typography.fontSize.sm }}>Data:</span>
          <span style={{ color: colors.accent_blue, fontWeight: 500, marginLeft: spacing.xs }}>{'No Analysis'}</span>
        </div>
        <button
          className="refresh-btn"
          onClick={() => window.location.reload()}
          style={{
            marginLeft: spacing.sm,
            padding: `${spacing.sm} ${spacing.md}`,
            background: 'transparent',
            border: `1px solid ${colors.border}`,
            color: colors.text_secondary,
            fontSize: typography.fontSize.sm,
            borderRadius: radius.md,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: spacing.xs,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          Refresh
        </button>
      </div>
    </header>
  )
}

export const MainContent = ({ children, pageTitle }: any) => {
  return (
    <main className="main-content" style={{ marginLeft: sidebarWidth, transitionMargin: 'margin-left 0.3s ease' }}>
      <div className="page-header">
        <h2 style={{ color: colors.text_primary, fontSize: typography.fontSize['2xl'], fontWeight: 600 }}>{pageTitle}</h2>
      </div>
      {children}
    </main>
  )
}