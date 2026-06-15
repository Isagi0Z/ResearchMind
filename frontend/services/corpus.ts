import { apiClient } from "@/lib/api-client";
import { RUODocument } from "@/types/document";

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

export async function getDocuments(params: GetDocumentsParams): Promise<PaginatedResponse<RUODocument>> {
  const queryParams = new URLSearchParams({
    pageIndex: params.pageIndex.toString(),
    pageSize: params.pageSize.toString(),
  });
  
  return await apiClient.get<PaginatedResponse<RUODocument>>(`/api/v1/documents?${queryParams.toString()}`);
}

export async function getDocument(id: string): Promise<RUODocument> {
  return await apiClient.get<RUODocument>(`/api/v1/documents/${id}`);
}
