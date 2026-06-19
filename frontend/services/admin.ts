import { apiClient } from "@/lib/api-client";
import { PaginatedUsersResponse, UserDetail, UpdateUserRoleRequest, UpdateUserStatusRequest } from "@/types/admin";

export interface ListUsersParams {
  pageIndex: number;
  pageSize: number;
  searchQuery?: string;
  sortBy?: string;
  sortDirection?: "asc" | "desc";
}

export async function listUsers(params: ListUsersParams): Promise<PaginatedUsersResponse> {
  const queryParams = new URLSearchParams({
    pageIndex: params.pageIndex.toString(),
    pageSize: params.pageSize.toString(),
  });
  if (params.searchQuery) queryParams.set("searchQuery", params.searchQuery);
  if (params.sortBy) queryParams.set("sortBy", params.sortBy);
  if (params.sortDirection) queryParams.set("sortDirection", params.sortDirection);

  return await apiClient.get<PaginatedUsersResponse>(`/api/v1/admin/users?${queryParams.toString()}`);
}

export async function getUser(id: string): Promise<UserDetail> {
  return await apiClient.get<UserDetail>(`/api/v1/admin/users/${id}`);
}

export async function updateUserRole(id: string, role: string): Promise<UserDetail> {
  return await apiClient.patch<UserDetail, UpdateUserRoleRequest>(`/api/v1/admin/users/${id}/role`, { role });
}

export async function updateUserStatus(id: string, is_active: boolean): Promise<UserDetail> {
  return await apiClient.patch<UserDetail, UpdateUserStatusRequest>(`/api/v1/admin/users/${id}/status`, { is_active });
}
