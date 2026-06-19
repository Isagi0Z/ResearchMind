import { Metadata } from "next"
import { AdminUsers } from "@/features/admin/admin-users"

export const metadata: Metadata = {
  title: "Admin Console - ResearchMind",
  description: "User management and administration.",
}

export default function AdminPage() {
  return (
    <div className="h-full">
      <AdminUsers />
    </div>
  )
}
