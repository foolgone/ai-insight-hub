import clsx from 'clsx'

const SIZE_CLASSES = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-16 w-16 text-lg',
}

const COLORS = [
  'bg-primary-100 text-primary-700',
  'bg-success-50 text-success-700',
  'bg-warning-50 text-warning-700',
  'bg-info-50 text-info-700',
  'bg-error-50 text-error-700',
]

function hashColor(name) {
  let hash = 0
  for (let index = 0; index < String(name).length; index += 1) {
    hash = (hash + String(name).charCodeAt(index)) % COLORS.length
  }
  return COLORS[hash]
}

/**
 * 头像（02 §2.10）：优先图片，无图时显示首字母 + 哈希背景色。
 * @param {{
 *   src?: string,
 *   name?: string,
 *   size?: 'sm'|'md'|'lg',
 *   className?: string,
 * }} props
 */
export function Avatar({ src, name = '', size = 'md', className }) {
  if (src) {
    return (
      <img
        src={src}
        alt={name || '头像'}
        className={clsx('shrink-0 rounded-full object-cover', SIZE_CLASSES[size], className)}
      />
    )
  }

  return (
    <span
      aria-label={name || '头像'}
      role="img"
      className={clsx(
        'grid shrink-0 place-items-center rounded-full font-medium uppercase',
        SIZE_CLASSES[size],
        hashColor(name || 'U'),
        className
      )}
    >
      {(name || 'U').slice(0, 1)}
    </span>
  )
}
