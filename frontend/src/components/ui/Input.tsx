import React from 'react'

export const Input = ({ type = 'text', value, onChange, placeholder, disabled, style, className }: any) => {
  return (
    <input
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      style={style}
      className={className}
    />
  )
}