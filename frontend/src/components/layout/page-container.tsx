"use client"

import * as React from "react"
import { Sidebar } from "./sidebar"
import { Header } from "./header"
import { Menu, X } from "lucide-react"

import { ProtectedRoute } from "./protected-route"

interface PageContainerProps {
  title: string
  children: React.ReactNode
}

export function PageContainer({ title, children }: PageContainerProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false)

  return (
    <ProtectedRoute>
      <div className="flex h-screen w-full bg-slate-950 text-slate-50 overflow-hidden">
        {/* Desktop Sidebar */}
        <div className="hidden md:flex z-20">
          <Sidebar />
        </div>

        {/* Mobile Sidebar Overlay */}
        {isMobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-40 flex">
            {/* Backdrop */}
            <div 
              className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity" 
              onClick={() => setIsMobileMenuOpen(false)}
            />
            {/* Sidebar Panel */}
            <div className="relative flex w-64 max-w-xs flex-1 flex-col bg-slate-950 shadow-2xl ring-1 ring-slate-800">
              <div className="absolute top-0 right-0 -mr-12 pt-2">
                <button
                  type="button"
                  className="ml-1 flex h-10 w-10 items-center justify-center rounded-full focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white"
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

        <div className="flex flex-1 flex-col overflow-hidden relative">
          <div className="flex items-center border-b border-slate-800 bg-slate-950/80 backdrop-blur-md h-16 w-full">
            <button
              type="button"
              className="px-4 text-slate-400 md:hidden hover:text-white"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <span className="sr-only">Open sidebar</span>
              <Menu className="h-6 w-6" aria-hidden="true" />
            </button>
            <div className="flex-1 w-full">
              <Header title={title} />
            </div>
          </div>

          <main className="flex-1 overflow-y-auto bg-slate-950">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </ProtectedRoute>
  )
}
