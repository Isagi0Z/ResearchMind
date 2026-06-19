import { apiClient } from "@/lib/api-client";
import { CorpusSummary, SystemStatus, RecentReview } from "@/types/dashboard";
import { DocumentListItem } from "@/types/document-list-item";

export async function getCorpusSummary(): Promise<CorpusSummary> {
  return await apiClient.get<CorpusSummary>("/api/v1/dashboard/summary");
}

export async function getRecentDocuments(): Promise<DocumentListItem[]> {
  // Use documents endpoint to get recent documents
  const res = await apiClient.get<{data: DocumentListItem[], total: number}>("/api/v1/documents?pageIndex=0&pageSize=10");
  return res.data;
}

export async function getSystemStatus(): Promise<SystemStatus> {
  return await apiClient.get<SystemStatus>("/api/v1/dashboard/status");
}

export async function getRecentReviews(): Promise<RecentReview[]> {
  return await apiClient.get<RecentReview[]>("/api/v1/dashboard/recent");
}
