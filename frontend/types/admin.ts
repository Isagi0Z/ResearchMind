export interface UserListItem {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface UserDetail {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface PaginatedUsersResponse {
  data: UserListItem[]
  total: number
}

export interface UpdateUserRoleRequest {
  role: string
}

export interface UpdateUserStatusRequest {
  is_active: boolean
}
