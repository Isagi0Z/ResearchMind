import { useQuery } from "@tanstack/react-query";
import { getCorpusSummary, getRecentDocuments, getSystemStatus, getRecentReviews } from "@/services/dashboard";

export function useCorpusSummary() {
  return useQuery({
    queryKey: ["dashboard", "corpus-summary"],
    queryFn: getCorpusSummary,
  });
}

export function useRecentDocuments() {
  return useQuery({
    queryKey: ["dashboard", "recent-documents"],
    queryFn: getRecentDocuments,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["dashboard", "system-status"],
    queryFn: getSystemStatus,
  });
}

export function useRecentReviews() {
  return useQuery({
    queryKey: ["dashboard", "recent-reviews"],
    queryFn: getRecentReviews,
  });
}
