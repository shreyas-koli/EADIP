"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Database, LayoutDashboard, History, Settings, Shield, Search, Compass } from "lucide-react"
import { cn } from "@/lib/utils"

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Warehouses", href: "/warehouses", icon: Database },
  { name: "Warehouse Explorer", href: "/explorer", icon: Compass },
  { name: "Discovery", href: "/discovery", icon: Search },
  { name: "History", href: "/history", icon: History },
  { name: "Settings", href: "/settings", icon: Settings },
]

interface SidebarProps {
  onNavigate?: () => void
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col border-r border-slate-800 bg-slate-950">
      <div className="flex h-16 items-center px-6 border-b border-slate-800">
        <Shield className="h-6 w-6 text-blue-500 mr-2" />
        <span className="text-lg font-bold tracking-tight text-slate-100">EADIP</span>
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-3">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/")
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => {
                  if (onNavigate) onNavigate()
                }}
                className={cn(
                  "group flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-slate-800 text-white"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-white"
                )}
              >
                <item.icon
                  className={cn(
                    "mr-3 h-5 w-5 flex-shrink-0",
                    isActive ? "text-blue-500" : "text-slate-500 group-hover:text-slate-300"
                  )}
                  aria-hidden="true"
                />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
