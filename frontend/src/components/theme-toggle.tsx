import { Monitor, Moon, Sun } from 'lucide-react'

import { useTheme, type Theme } from '@/components/theme-provider'
import { Button } from '@/components/ui/button'

const NEXT: Record<Theme, Theme> = { light: 'dark', dark: 'system', system: 'light' }
const LABEL: Record<Theme, string> = { light: 'Light', dark: 'Dark', system: 'System' }

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const Icon = theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => setTheme(NEXT[theme])}
      aria-label={`Theme: ${LABEL[theme]}. Click to change.`}
    >
      <Icon />
      {LABEL[theme]}
    </Button>
  )
}
