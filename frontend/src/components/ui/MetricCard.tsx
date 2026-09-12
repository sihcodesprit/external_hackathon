import React from 'react'

export const Card = ({ children, className, style }: any) => {
  return (
    <div className={`card ${className || ''}`} style={style}>
      {children}
    </div>
  )
}

export const MetricCard = ({ title, value, subtitle, icon, bgColor }: any) => {
  return (
    <div className="metric-card" style={{ bgColor }}>
      <h3 style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
        {title}
      </h3>
      <div style={{ color: 'var(--value)', fontSize: '2rem', fontWeight: '600' }}>
        {value}
      </div>
      <p style={{ color: 'var(--subtitle)', fontSize: '0.75rem' }}>
        {subtitle}
      </p>
    </div>
  )
}