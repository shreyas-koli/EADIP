"use client"

import * as React from "react"
import { authApi, User, LoginRequest, RegisterRequest } from "@/lib/api/auth"

interface AuthContextType {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (data: LoginRequest) => Promise<void>
  register: (data: RegisterRequest) => Promise<void>
  logout: () => void
}

const AuthContext = React.createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<User | null>(null)
  const [isLoading, setIsLoading] = React.useState(true)

  React.useEffect(() => {
    // Check for existing token and fetch user on mount
    const checkAuth = async () => {
      const token = localStorage.getItem("access_token")
      if (token) {
        try {
          const userData = await authApi.getMe()
          setUser(userData)
        } catch {
          // Token is likely invalid/expired
          localStorage.removeItem("access_token")
        }
      }
      setIsLoading(false)
    }

    checkAuth()
  }, [])

  const login = async (data: LoginRequest) => {
    const response = await authApi.login(data)
    localStorage.setItem("access_token", response.access_token)
    const userData = await authApi.getMe()
    setUser(userData)
  }

  const register = async (data: RegisterRequest) => {
    await authApi.register(data)
    // Auto login after successful registration
    await login({ email: data.email, password: data.password })
  }

  const logout = () => {
    localStorage.removeItem("access_token")
    setUser(null)
  }

  const value = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = React.useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
