"use client"

import { useState, useCallback } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { listUsers, updateUserRole, updateUserStatus } from "@/services/admin"
import { LoadingState } from "@/components/shared/loading-state"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { useAuthStore } from "@/stores/auth-store"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import Link from "next/link"
import { Search, Shield, ShieldOff, UserCheck, UserX, Users, Loader2 } from "lucide-react"

interface ApiError {
  status: number
  message: string
}

export function AdminUsers() {
  const isAdmin = useAuthStore((s) => s.isAdmin())
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [pageIndex, setPageIndex] = useState(0)
  const pageSize = 10

  const searchTimerRef = useState<ReturnType<typeof setTimeout> | null>(null)

  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
    if (searchTimerRef[0]) clearTimeout(searchTimerRef[0])
    searchTimerRef[0] = setTimeout(() => {
      setDebouncedSearch(value)
      setPageIndex(0)
    }, 300)
  }, [searchTimerRef])

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin-users", debouncedSearch, pageIndex],
    queryFn: () => listUsers({
      pageIndex,
      pageSize,
      searchQuery: debouncedSearch || undefined,
      sortBy: "created_at",
      sortDirection: "desc",
    }),
    retry: false,
  })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => updateUserRole(id, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) => updateUserStatus(id, is_active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-users"] }),
  })

  const apiError = error as ApiError | null

  if (!isAdmin && !isLoading && isError) {
    const status = apiError?.status
    if (status === 403) {
      return (
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Admin Console</h1>
            <p className="text-muted-foreground mt-1">User management and administration.</p>
          </div>
          <ErrorState
            title="Access Restricted"
            description="The admin console requires administrator privileges."
          />
        </div>
      )
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Console</h1>
          <p className="text-muted-foreground mt-1">User management and administration.</p>
        </div>
        <LoadingState />
      </div>
    )
  }

  if (isError) {
    const status = apiError?.status

    if (status === 401) {
      return (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Card className="w-full max-w-md">
            <CardContent className="p-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto">
                <ShieldOff className="w-8 h-8 text-muted-foreground" />
              </div>
              <h2 className="text-xl font-bold">Authentication Required</h2>
              <p className="text-muted-foreground">
                You need to be logged in to access the admin console. Please log in and try again.
              </p>
              <Button asChild>
                <Link href="/login">Go to Login</Link>
              </Button>
            </CardContent>
          </Card>
        </div>
      )
    }

    if (status === 403) {
      return (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Card className="w-full max-w-md border-amber-500/30">
            <CardContent className="p-8 text-center space-y-4">
              <div className="w-16 h-16 rounded-full bg-amber-500/10 flex items-center justify-center mx-auto">
                <Shield className="w-8 h-8 text-amber-500" />
              </div>
              <h2 className="text-xl font-bold">Access Restricted</h2>
              <p className="text-muted-foreground">
                The admin console requires administrator privileges.
                Contact your administrator to request access.
              </p>
            </CardContent>
          </Card>
        </div>
      )
    }

    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Console</h1>
          <p className="text-muted-foreground mt-1">User management and administration.</p>
        </div>
        <ErrorState
          title="Failed to load users"
          description={apiError?.message || "An unexpected error occurred."}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  const users = data?.data || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Console</h1>
          <p className="text-muted-foreground mt-1">
            {total} registered user{total !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search users by username or email..."
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="pl-8"
          />
        </div>
      </div>

      {users.length === 0 ? (
        <EmptyState
          title="No users found"
          description={debouncedSearch ? "Try a different search term." : "No users have been registered yet."}
          icon={<Users className="w-8 h-8 text-muted-foreground" />}
        />
      ) : (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Username</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Registered</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">{user.username}</TableCell>
                  <TableCell className="text-muted-foreground">{user.email}</TableCell>
                  <TableCell>
                    <Select
                      value={user.role}
                      onValueChange={(role) => roleMutation.mutate({ id: user.id, role })}
                      disabled={roleMutation.isPending && roleMutation.variables?.id === user.id}
                    >
                      <SelectTrigger className="w-24 h-8 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">user</SelectItem>
                        <SelectItem value="admin">admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant="outline"
                      className={
                        user.is_active
                          ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800"
                          : "bg-destructive/10 text-destructive border-destructive/20"
                      }
                    >
                      {user.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {user.is_active ? (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => statusMutation.mutate({ id: user.id, is_active: false })}
                          disabled={statusMutation.isPending && statusMutation.variables?.id === user.id}
                          title="Deactivate user"
                        >
                          {statusMutation.isPending && statusMutation.variables?.id === user.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <UserX className="h-4 w-4" />
                          )}
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-emerald-600"
                          onClick={() => statusMutation.mutate({ id: user.id, is_active: true })}
                          disabled={statusMutation.isPending && statusMutation.variables?.id === user.id}
                          title="Activate user"
                        >
                          {statusMutation.isPending && statusMutation.variables?.id === user.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <UserCheck className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t">
              <p className="text-sm text-muted-foreground">
                Page {pageIndex + 1} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pageIndex === 0}
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={pageIndex >= totalPages - 1}
                  onClick={() => setPageIndex((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
