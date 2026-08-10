import { apiAssetUrl, cn, rolePersona } from '@/lib/utils'

type AvatarUser = {
  name?: string | null
  role?: string | null
  avatar_url?: string | null
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-16 w-16 text-xl',
  xl: 'h-24 w-24 text-3xl',
}

export default function UserAvatar({
  user,
  size = 'md',
  className,
}: {
  user?: AvatarUser | null
  size?: keyof typeof sizeClasses
  className?: string
}) {
  const persona = rolePersona(user?.role)
  const imageUrl = apiAssetUrl(user?.avatar_url)
  const initials = (user?.name || '?')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-cover bg-center font-bold text-white shadow-sm ring-1 ring-white/40',
        sizeClasses[size],
        imageUrl ? 'bg-slate-200' : `bg-gradient-to-br ${persona.gradient}`,
        className,
      )}
      style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined}
      aria-hidden="true"
    >
      {!imageUrl && initials}
    </span>
  )
}
