import React from 'react'

export const Button = ({ variant = 'primary', children, style, className, onClick }: any) => {
  const variants = {
    primary: 'bg-blue text-white hover:bg-cyan',
    outline: 'border-blue text-blue hover:bg-blue/10',
    secondary: 'border-gray text-gray hover:bg-gray/10',
    danger: 'bg-red text-white hover:bg-orange',
    warning: 'bg-orange text-white hover:bg-yellow',
    success: 'bg-green text-white hover:bg-green/80',
  }

  const variantStyles = {
    primary: 'px-4 py-2 rounded-md font-medium',
    outline: 'px-4 py-2 rounded-md border-2 border-blue text-blue font-medium',
    secondary: 'px-4 py-2 rounded-md border border-gray text-gray hover:bg-gray/10',
    danger: 'px-4 py-2 rounded-md bg-red text-white',
    warning: 'px-4 py-2 rounded-md bg-orange text-white',
    success: 'px-4 py-2 rounded-md bg-green text-white',
  }

  const classNames = variants[variant] || variants.primary
  const styleNames = styleStyles[variant] || styleStyles.primary

  return (
    <button
      type="button"
      className={classNames}
      style={style}
      onClick={onClick}
      className={className}
    >
      {children}
    </button>
  )
}