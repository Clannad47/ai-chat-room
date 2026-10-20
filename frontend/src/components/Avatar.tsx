import type { CSSProperties } from 'react'

type Props = {
  name: string
  kind: 'user' | 'bot'
  size?: 'sm' | 'md'
}

export function Avatar({ name, kind, size = 'md' }: Props) {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) % 360

  const parts = name.trim().split(/\s+/).filter(Boolean)
  const label =
    parts.length === 0
      ? '?'
      : parts.length === 1
        ? parts[0].slice(0, 2).toUpperCase()
        : `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()

  return (
    <span
      className={`avatar avatar-${kind} avatar-${size}`}
      style={{ '--avatar-hue': hash } as CSSProperties}
      aria-hidden="true"
    >
      {label}
    </span>
  )
}
