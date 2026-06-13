"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { LayoutDashboard, Database, Activity, Network, FileSearch, Sparkles, Menu, X, CheckCircle, AlertTriangle, XCircle, Moon, Sun, Monitor } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useUIStore } from "@/stores/ui-store"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useTheme } from "next-themes"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

const NAV_ITEMS: { title: string; href: string; icon: any; disabled: boolean; description?: string }[] = [
  { title: "Dashboard", href: "/dashboard", icon: LayoutDashboard, disabled: false },
  { title: "Corpus Manager", href: "/corpus", icon: Database, disabled: false },
  { title: "Graph Explorer", href: "/graph", icon: Network, disabled: false },
  { title: "Query Interface", href: "/query", icon: FileSearch, disabled: false },
  { title: "Review Generator", href: "/reviews", icon: Sparkles, disabled: false },
  { title: "System Monitoring", href: "/monitoring", icon: Activity, disabled: false },
]

export function Sidebar() {
  const pathname = usePathname()
  const { sidebarCollapsed, setSidebarCollapsed } = useUIStore()

  return (
    <aside
      className={cn(
        "hidden md:flex flex-col border-r bg-card transition-all duration-300 ease-in-out",
        sidebarCollapsed ? "w-[80px]" : "w-[240px]"
      )}
    >
      <div className="flex h-16 items-center border-b px-4 py-4 justify-between">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2 font-bold text-xl tracking-tight">
            <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
              <Database className="w-5 h-5 text-primary-foreground" />
            </div>
            ResearchMind
          </div>
        )}
        {sidebarCollapsed && (
          <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center mx-auto">
            <Database className="w-5 h-5 text-primary-foreground" />
          </div>
        )}
      </div>

      <ScrollArea className="flex-1 py-4">
        <nav className="flex flex-col gap-2 px-2">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
            const Icon = item.icon

            const content = (
              <div
                className={cn(
                  "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-secondary text-secondary-foreground"
                    : "hover:bg-muted hover:text-foreground",
                  item.disabled ? "opacity-50 cursor-not-allowed hover:bg-transparent" : "cursor-pointer",
                  sidebarCollapsed ? "justify-center" : "justify-start"
                )}
              >
                <Icon className={cn("h-5 w-5", !sidebarCollapsed && "mr-3", isActive ? "text-primary" : "text-muted-foreground")} />
                {!sidebarCollapsed && (
                  <div className="flex flex-1 items-center justify-between">
                    <span>{item.title}</span>
                    {item.disabled && (
                      <span className="text-[10px] uppercase tracking-wider font-semibold text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                        Soon
                      </span>
                    )}
                  </div>
                )}
              </div>
            )

            if (item.disabled) {
              return <div key={item.href} title={item.description}>{content}</div>
            }

            return (
              <Link key={item.href} href={item.href}>
                {content}
              </Link>
            )
          })}
        </nav>
      </ScrollArea>
      
      <div className="border-t p-4 flex justify-center">
         <Button 
           variant="ghost" 
           size="icon" 
           onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
           className="w-full text-muted-foreground hover:text-foreground"
         >
           <Menu className="h-5 w-5" />
         </Button>
      </div>
    </aside>
  )
}

function ThemeToggle() {
  const { setTheme } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme("light")}>
          <Sun className="mr-2 h-4 w-4" />
          <span>Light</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          <Moon className="mr-2 h-4 w-4" />
          <span>Dark</span>
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")}>
          <Monitor className="mr-2 h-4 w-4" />
          <span>System</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 border-b flex items-center justify-between px-6 bg-card sticky top-0 z-10">
          <div className="md:hidden font-bold flex items-center gap-2 text-xl">
             <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center">
              <Database className="w-5 h-5 text-primary-foreground" />
            </div>
            RM
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center font-semibold text-secondary-foreground">
              A
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-auto bg-muted/20">
          <div className="mx-auto w-full max-w-7xl p-4 md:p-6 lg:p-8">
             {children}
          </div>
        </main>
      </div>
    </div>
  )
}
