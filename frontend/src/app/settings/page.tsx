"use client"

import * as React from "react"
import { useAuth } from "@/contexts/auth-context"
import { PageContainer } from "@/components/layout/page-container"
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card"
import { User, Moon, Server, Shield, BadgeCheck } from "lucide-react"

export default function SettingsPage() {
  const { user } = useAuth()

  return (
    <PageContainer title="Settings">
      <div className="max-w-4xl space-y-8">
        
        {/* Profile Section */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-xl">
              <User className="mr-2 h-5 w-5 text-blue-500" /> Profile Information
            </CardTitle>
            <CardDescription>View your personal profile and role details.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-400">Full Name</label>
                <div className="h-10 w-full rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-200 cursor-not-allowed opacity-80">
                  {user?.full_name || "Unknown"}
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-400">Email Address</label>
                <div className="h-10 w-full rounded-md border border-slate-700 bg-slate-950/50 px-3 py-2 text-sm text-slate-200 cursor-not-allowed opacity-80">
                  {user?.email || "Unknown"}
                </div>
              </div>
            </div>
            
            <div className="flex items-center space-x-2 text-sm text-slate-400">
              <Shield className="h-4 w-4" />
              <span>Role: <strong className="text-slate-200 font-medium">Administrator</strong></span>
            </div>
            
            <p className="text-xs text-slate-500 italic border-t border-slate-800 pt-4 mt-2">
              Note: Profile modifications are currently managed by your organization administrator.
            </p>
          </CardContent>
        </Card>
        
        {/* Appearance Section */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-xl">
              <Moon className="mr-2 h-5 w-5 text-indigo-400" /> Appearance
            </CardTitle>
            <CardDescription>Manage your display preferences.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 rounded-lg border border-slate-700 bg-slate-800/50">
              <div>
                <p className="font-medium text-slate-200">Theme Preference</p>
                <p className="text-sm text-slate-400">EADIP currently defaults to a high-contrast dark theme for data visibility.</p>
              </div>
              <div className="px-3 py-1 rounded-full bg-indigo-500/20 text-indigo-300 text-xs font-semibold border border-indigo-500/30">
                Dark Mode Active
              </div>
            </div>
          </CardContent>
        </Card>

        {/* System Information */}
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center text-xl">
              <Server className="mr-2 h-5 w-5 text-emerald-500" /> System Information
            </CardTitle>
            <CardDescription>EADIP platform version and available capabilities.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg border border-slate-700 bg-slate-950/50 flex items-center justify-between">
                <span className="text-sm text-slate-400">Platform Version</span>
                <span className="text-sm font-mono text-slate-200">v1.0.0-beta</span>
              </div>
              <div className="p-4 rounded-lg border border-slate-700 bg-slate-950/50 flex items-center justify-between">
                <span className="text-sm text-slate-400">Discovery Engine</span>
                <span className="flex items-center text-sm font-medium text-emerald-400">
                  <BadgeCheck className="mr-1 h-4 w-4" /> 5 / 5 Agents Online
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

      </div>
    </PageContainer>
  )
}
