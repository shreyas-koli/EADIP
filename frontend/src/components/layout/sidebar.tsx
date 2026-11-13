"use client"

import * as React from "react"
import Link from "next/link"
import Image from "next/image"
import { usePathname } from "next/navigation"
import { 
  Database, 
  LayoutDashboard, 
  History, 
  Settings, 
  Search, 
  Compass, 
  ChevronLeft, 
  ChevronRight
} from "lucide-react"
import { cn } from "@/lib/utils"

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard, badge: null },
  { name: "Warehouses", href: "/warehouses", icon: Database, badge: null },
  { name: "Warehouse Explorer", href: "/explorer", icon: Compass, badge: "SQL" },
  { name: "Discovery", href: "/discovery", icon: Search, badge: "AI" },
  { name: "History", href: "/history", icon: History, badge: null },
  { name: "Settings", href: "/settings", icon: Settings, badge: null },
]

interface SidebarProps {
  onNavigate?: () => void
  isCollapsed?: boolean
  onToggleCollapse?: () => void
}

export function Sidebar({ onNavigate, isCollapsed = false, onToggleCollapse }: SidebarProps) {
  const pathname = usePathname()

  return (
    <aside 
      className={cn(
        "flex h-full flex-col border-r border-slate-800/80 bg-slate-950/95 backdrop-blur-xl transition-all duration-300 relative select-none",
        isCollapsed ? "w-20" : "w-64"
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between px-4 border-b border-slate-800/80">
        <Link 
          href="/dashboard"
          className="flex items-center gap-3 overflow-hidden group"
          onClick={() => onNavigate?.()}
        >
          <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl shadow-md transition-all group-hover:scale-105">
            <Image
              src="/aetherarchive-logo.png"
              alt="AetherArchive Logo"
              width={40}
              height={40}
              priority
              className="h-full w-full object-contain"
            />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col min-w-0">
              <span className="text-base font-extrabold tracking-tight text-white flex items-center gap-1.5">
                AetherArchive
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-widest text-cyan-400">
                Autonomous Data
              </span>
            </div>
          )}
        </Link>

        {/* Collapse toggle (desktop only) */}
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="hidden md:flex h-7 w-7 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:text-white hover:border-slate-700 transition-colors"
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </button>
        )}
      </div>

      {/* Navigation List */}
      <div className="flex-1 overflow-y-auto py-5 px-3">
        <div className="space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname?.startsWith(item.href))
            const Icon = item.icon

            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => onNavigate?.()}
                title={isCollapsed ? item.name : undefined}
                className={cn(
                  "group relative flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                  isActive
                    ? "bg-gradient-to-r from-blue-600/20 to-cyan-500/10 text-white border border-blue-500/30 shadow-sm"
                    : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200 border border-transparent"
                )}
              >
                {/* Active Indicator Bar */}
                {isActive && (
                  <div className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
                )}

                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0 transition-colors",
                    isActive
                      ? "text-cyan-400 drop-shadow-[0_0_6px_rgba(6,182,212,0.6)]"
                      : "text-slate-500 group-hover:text-slate-300",
                    isCollapsed ? "mx-auto" : "mr-3"
                  )}
                  aria-hidden="true"
                />

                {!isCollapsed && (
                  <div className="flex flex-1 items-center justify-between min-w-0">
                    <span className="truncate">{item.name}</span>
                    {item.badge && (
                      <span className="rounded-md bg-blue-500/15 px-1.5 py-0.5 text-[10px] font-bold text-blue-400 border border-blue-500/30">
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
              </Link>
            )
          })}
        </div>
      </div>

      {/* Bottom Status Panel */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/60">
        {!isCollapsed ? (
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/50 p-3">
            <div className="flex items-center justify-between mb-1.5">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                Engine Online
              </span>
              <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-1.5 py-0.2 rounded border border-cyan-800/40">
                v2.0
              </span>
            </div>
            <p className="text-[11px] text-slate-500">Autonomous multi-agent warehouse intelligence</p>
          </div>
        ) : (
          <div className="flex justify-center" title="Engine Online • v2.0">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
            </span>
          </div>
        )}
      </div>
    </aside>
  )
}
