"use client"

import * as React from "react"
import { useAuth } from "@/contexts/auth-context"
import { PageContainer } from "@/components/layout/page-container"
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card"
import { User, Moon, Shield, BadgeCheck, Cpu } from "lucide-react"

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <PageContainer title="Platform Settings">
      <div className="max-w-4xl space-y-8">
        {/* Banner */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 shadow-2xl backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-cyan-400">
              <Shield className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-xl font-extrabold text-white">System Settings & Operator Environment</h2>
              <p className="text-xs text-slate-400 mt-0.5">Manage operator profile, UI theme preferences, and multi-agent engine capabilities.</p>
            </div>
          </div>
        </div>
        
        {/* Profile Section */}
        <Card className="bg-slate-950/80 border-slate-800 shadow-xl">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-lg text-slate-100">
              <User className="mr-2 h-5 w-5 text-cyan-400" /> Operator Profile
            </CardTitle>
            <CardDescription className="text-xs text-slate-400">Personal authentication credentials and role permissions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">Full Name</label>
                <div className="h-10 w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-medium text-slate-200 cursor-not-allowed">
                  {user?.full_name || "Unknown Operator"}
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">Email Address</label>
                <div className="h-10 w-full rounded-xl border border-slate-800 bg-slate-900/60 px-3.5 py-2 text-xs font-mono text-slate-200 cursor-not-allowed">
                  {user?.email || "Unknown"}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-2 text-xs text-slate-400 bg-slate-900/50 p-3 rounded-xl border border-slate-800">
              <Shield className="h-4 w-4 text-emerald-400" />
              <span>Assigned Role: <strong className="text-slate-200 font-semibold">System Administrator / Database Operator</strong></span>
            </div>
          </CardContent>
        </Card>
        
        {/* Appearance Section */}
        <Card className="bg-slate-950/80 border-slate-800 shadow-xl">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-lg text-slate-100">
              <Moon className="mr-2 h-5 w-5 text-indigo-400" /> Studio Appearance
            </CardTitle>
            <CardDescription className="text-xs text-slate-400">Manage display aesthetics and high-contrast workspace settings.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 rounded-xl border border-slate-800 bg-slate-900/50">
              <div>
                <p className="text-sm font-semibold text-slate-200">High-Contrast Deep Slate Theme</p>
                <p className="text-xs text-slate-400 mt-0.5">Optimized for SQL console readability, SVG data visualizations, and real-time streaming telemetry.</p>
              </div>
              <div className="px-3 py-1 rounded-full bg-cyan-950/80 text-cyan-300 text-xs font-semibold border border-cyan-700/50">
                Active
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Information */}
        <Card className="bg-slate-950/80 border-slate-800 shadow-xl">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-lg text-slate-100">
              <Cpu className="mr-2 h-5 w-5 text-emerald-400" /> Platform Architecture & Engine
            </CardTitle>
            <CardDescription className="text-xs text-slate-400">AetherArchive Autonomous Intelligence release information.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">Platform Version</span>
                <span className="text-xs font-mono font-bold text-cyan-400">v2.0.0 (Enterprise)</span>
              </div>
              <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">Discovery Intelligence</span>
                <span className="flex items-center text-xs font-medium text-emerald-400">
                  <BadgeCheck className="mr-1 h-4 w-4" /> 6 / 6 Autonomous Agents Online
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  )
}
