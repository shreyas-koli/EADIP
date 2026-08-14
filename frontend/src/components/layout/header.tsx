import { Bell, User, Moon, LogOut } from "lucide-react"
import { useAuth } from "@/contexts/auth-context"

interface HeaderProps {
  title: string
}

export function Header({ title }: HeaderProps) {
  const { user, logout } = useAuth()

  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-x-4 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md px-4 sm:gap-x-6 sm:px-6 lg:px-8">
      <div className="flex flex-1 gap-x-4 self-stretch lg:gap-x-6">
        <div className="flex flex-1 items-center">
          <h1 className="text-xl font-semibold text-slate-100">{title}</h1>
        </div>
        <div className="flex items-center gap-x-4 lg:gap-x-6">
          <button type="button" className="-m-2.5 p-2.5 text-slate-400 hover:text-slate-300">
            <span className="sr-only">View notifications</span>
            <Bell className="h-5 w-5" aria-hidden="true" />
          </button>

          {/* Theme toggle placeholder */}
          <button type="button" className="-m-2.5 p-2.5 text-slate-400 hover:text-slate-300">
            <span className="sr-only">Toggle theme</span>
            <Moon className="h-5 w-5" aria-hidden="true" />
          </button>

          {/* Separator */}
          <div className="hidden lg:block lg:h-6 lg:w-px lg:bg-slate-800" aria-hidden="true" />

          {/* Profile dropdown placeholder */}
          <div className="flex items-center gap-x-4">
            <button type="button" className="-m-1.5 flex items-center p-1.5 text-slate-400 hover:text-slate-300">
              <span className="sr-only">Open user menu</span>
              <div className="h-8 w-8 rounded-full bg-slate-800 flex items-center justify-center">
                <User className="h-4 w-4" />
              </div>
              <span className="hidden lg:flex lg:items-center">
                <span className="ml-4 text-sm font-semibold leading-6 truncate max-w-[150px]" aria-hidden="true">
                  {user?.full_name || "User"}
                </span>
              </span>
            </button>
            <button 
              type="button" 
              onClick={logout}
              className="ml-2 p-1.5 text-slate-400 hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
