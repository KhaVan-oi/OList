import { buttonVariants } from "@/components/ui/button.tsx"
import { cn } from "@/lib/utils.ts"
import { CalendarDaysIcon, ChartColumnIcon, LayoutDashboardIcon, LightbulbIcon, PackageIcon, StoreIcon, UsersIcon, type LucideIcon } from "lucide-react"
import { NavLink, Outlet } from "react-router-dom"

const links: { to: string; label: string; end: boolean; icon: LucideIcon }[] = [
  { to: "/", label: "Tổng quan", end: true, icon: LayoutDashboardIcon },
  { to: "/thoi-gian", label: "Thời gian", end: false, icon: CalendarDaysIcon },
  { to: "/hang-hoa", label: "Khu vực", end: false, icon: PackageIcon },
  { to: "/seller", label: "Người bán", end: false, icon: StoreIcon },
  { to: "/khach", label: "Khách hàng", end: false, icon: UsersIcon },
  { to: "/quyet-dinh", label: "Quyết định", end: false, icon: LightbulbIcon },
]

export function MainLayout() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-60 shrink-0 flex-col gap-6 border-r border-sidebar-border bg-sidebar px-4 py-5 text-sidebar-foreground">
        <div className="flex items-center gap-3 px-2">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <ChartColumnIcon className="size-5" />
          </span>
          <span className="text-lg font-bold tracking-[0.3px]">Olist</span>
        </div>
        <nav className="flex flex-col gap-1">
          {links.map((link) => {
            const Icon = link.icon
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn(buttonVariants({ variant: isActive ? "default" : "ghost", size: "default" }), "h-10 w-full justify-start rounded-xl px-3")
                }
              >
                <Icon data-icon="inline-start" />
                {link.label}
              </NavLink>
            )
          })}
        </nav>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
