import { apiClient } from "@/lib/api-client";
import { DocumentListItem } from "@/types/document-list-item";

export interface GetDocumentsParams {
  pageIndex: number;
  pageSize: number;
  searchQuery?: string;
  sortBy?: string;
  sortDirection?: "asc" | "desc";
  filters?: {
    yearRange?: [number, number];
    authors?: string[];
    source?: string[];
    status?: string[];
  };
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
}

export async function getDocuments(params: GetDocumentsParams): Promise<PaginatedResponse<DocumentListItem>> {
  const queryParams = new URLSearchParams({
    pageIndex: params.pageIndex.toString(),
    pageSize: params.pageSize.toString(),
  });
  if (params.searchQuery) queryParams.set("searchQuery", params.searchQuery);
  if (params.sortBy) queryParams.set("sortBy", params.sortBy);
  if (params.sortDirection) queryParams.set("sortDirection", params.sortDirection);

  return await apiClient.get<PaginatedResponse<DocumentListItem>>(`/api/v1/documents?${queryParams.toString()}`);
}
