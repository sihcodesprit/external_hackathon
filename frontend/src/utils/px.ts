export const px = (value: number | string) => {
  if (typeof value === 'number') return `${value}px`
  return value
}

export const rem = (value: number) => `${value}rem`