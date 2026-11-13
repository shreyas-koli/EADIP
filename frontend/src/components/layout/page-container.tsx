"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Header } from "./header"
import { CommandPalette } from "./command-palette"
import { Menu, X } from "lucide-react"
import { ProtectedRoute } from "./protected-route"

interface PageContainerProps {
  title: string
  breadcrumbs?: { label: string; href?: string }[]
  children: React.ReactNode
  fullWidth?: boolean
}

export function PageContainer({ title, breadcrumbs, children, fullWidth = false }: PageContainerProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false)
  const [isCollapsed, setIsCollapsed] = React.useState(false)
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = React.useState(false)

  // Global Cmd+K / Ctrl+K shortcut
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        setIsCommandPaletteOpen((prev) => !prev)
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return (
    <ProtectedRoute>
      <div className="flex h-screen w-full bg-slate-950 text-slate-50 overflow-hidden font-sans">
        {/* Desktop Collapsible Sidebar */}
        <div className="hidden md:flex z-20 shrink-0">
          <Sidebar 
            isCollapsed={isCollapsed} 
            onToggleCollapse={() => setIsCollapsed(!isCollapsed)} 
          />
        </div>

        {/* Mobile Sidebar Overlay */}
        {isMobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-40 flex">
            {/* Backdrop */}
            <div 
              className="fixed inset-0 bg-slate-950/80 backdrop-blur-md transition-opacity" 
              onClick={() => setIsMobileMenuOpen(false)}
            />
            {/* Drawer */}
            <div className="relative flex w-64 max-w-xs flex-1 flex-col bg-slate-950 shadow-2xl ring-1 ring-slate-800">
              <div className="absolute top-0 right-0 -mr-12 pt-3">
                <button
                  type="button"
                  className="flex h-10 w-10 items-center justify-center rounded-full text-slate-400 hover:text-white focus:outline-none"
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  <span className="sr-only">Close sidebar</span>
                  <X className="h-6 w-6 text-white" aria-hidden="true" />
                </button>
              </div>
              <Sidebar onNavigate={() => setIsMobileMenuOpen(false)} />
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex flex-1 flex-col overflow-hidden relative min-w-0">
          {/* Header Bar */}
          <div className="flex items-center w-full">
            <button
              type="button"
              className="px-4 text-slate-400 md:hidden hover:text-white h-16 flex items-center border-b border-slate-800 bg-slate-950"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <span className="sr-only">Open navigation</span>
              <Menu className="h-6 w-6" aria-hidden="true" />
            </button>
            <div className="flex-1 min-w-0">
              <Header 
                title={title} 
                breadcrumbs={breadcrumbs}
                onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} 
              />
            </div>
          </div>

          {/* Scrollable Page Body */}
          <main className="flex-1 overflow-y-auto bg-slate-950 relative">
            <div className={`mx-auto ${fullWidth ? "w-full px-4 sm:px-6 lg:px-8 py-6" : "max-w-7xl px-4 sm:px-6 lg:px-8 py-8"}`}>
              {children}
            </div>
          </main>
        </div>

        {/* Global Command Palette */}
        <CommandPalette 
          isOpen={isCommandPaletteOpen} 
          onClose={() => setIsCommandPaletteOpen(false)} 
        />
      </div>
    </ProtectedRoute>
  )
}
