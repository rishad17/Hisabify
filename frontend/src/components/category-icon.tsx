import {
  BookOpen,
  Briefcase,
  CirclePlus,
  Clapperboard,
  Ellipsis,
  Gift,
  GraduationCap,
  HandCoins,
  HeartPulse,
  House,
  Laptop,
  Receipt,
  RotateCcw,
  ShoppingBag,
  ShoppingBasket,
  Smartphone,
  Tag,
  Utensils,
  Bus,
  type LucideIcon,
} from 'lucide-react'

/**
 * Category icons are stored as lucide names in the database (e.g. "utensils").
 * An explicit map keeps the bundle small (importing every lucide icon is ~1 MB).
 */
const ICONS: Record<string, LucideIcon> = {
  utensils: Utensils,
  'shopping-basket': ShoppingBasket,
  bus: Bus,
  house: House,
  receipt: Receipt,
  smartphone: Smartphone,
  'graduation-cap': GraduationCap,
  'heart-pulse': HeartPulse,
  'shopping-bag': ShoppingBag,
  clapperboard: Clapperboard,
  gift: Gift,
  ellipsis: Ellipsis,
  briefcase: Briefcase,
  'hand-coins': HandCoins,
  'book-open': BookOpen,
  laptop: Laptop,
  'rotate-ccw': RotateCcw,
  'plus-circle': CirclePlus,
}

export function CategoryIcon({ name, className }: { name: string | null; className?: string }) {
  const Icon = (name && ICONS[name]) || Tag
  return <Icon className={className} aria-hidden />
}
