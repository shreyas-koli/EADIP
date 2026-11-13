"use client"

import * as React from "react"
import { User, LogOut, Search } from "lucide-react"
import { useAuth } from "@/contexts/auth-context"

interface HeaderProps {
  title: string
  breadcrumbs?: { label: string; href?: string }[]
  onOpenCommandPalette?: () => void
}

export function Header({ title, breadcrumbs, onOpenCommandPalette }: HeaderProps) {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl px-4 sm:px-6 lg:px-8">
      {/* Left: Breadcrumbs & Title */}
      <div className="flex items-center gap-3 min-w-0">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="font-semibold text-slate-300">AetherArchive</span>
          <span className="text-slate-600">/</span>
          {breadcrumbs?.map((crumb, idx) => (
            <React.Fragment key={idx}>
              <span className="text-slate-400">{crumb.label}</span>
              <span className="text-slate-600">/</span>
            </React.Fragment>
          ))}
          <span className="text-cyan-400 font-medium truncate">{title}</span>
        </div>
      </div>

      {/* Center: Spotlight Search / Command Palette Bar */}
      <div className="hidden md:flex flex-1 max-w-md mx-6">
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="w-full flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs text-slate-400 hover:border-slate-700 hover:bg-slate-900 hover:text-slate-200 transition-all shadow-inner group"
        >
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-slate-500 group-hover:text-cyan-400 transition-colors" />
            <span>Search or command jump...</span>
          </div>
          <div className="flex items-center gap-1 font-mono text-[10px] text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700">
            <span>⌘</span>
            <span>K</span>
          </div>
        </button>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Connection status pill */}
        <div className="hidden sm:flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-950/40 px-2.5 py-1 text-[11px] text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span>Connected</span>
        </div>

        {/* Command palette mobile button */}
        <button
          type="button"
          onClick={onOpenCommandPalette}
          className="md:hidden p-2 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-900"
          title="Search"
        >
          <Search className="h-4 w-4" />
        </button>

        {/* Separator */}
        <div className="h-5 w-px bg-slate-800" aria-hidden="true" />

        {/* User Info & Logout */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-2.5 py-1 px-2 rounded-lg bg-slate-900/40 border border-slate-800/60">
            <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-blue-600 to-cyan-500 flex items-center justify-center text-white text-xs font-bold shadow-sm">
              {user?.full_name ? user.full_name[0].toUpperCase() : <User className="h-3.5 w-3.5" />}
            </div>
            <div className="hidden lg:flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-200 truncate max-w-[120px]">
                {user?.full_name || "User"}
              </span>
              <span className="text-[10px] text-slate-400 truncate max-w-[120px]">
                {user?.email || "Operator"}
              </span>
            </div>
          </div>

          <button 
            type="button" 
            onClick={logout}
            className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded-lg transition-colors"
            title="Sign out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  )
}
