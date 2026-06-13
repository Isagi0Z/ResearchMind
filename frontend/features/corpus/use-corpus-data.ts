import { useQuery } from "@tanstack/react-query";
import { getDocuments, GetDocumentsParams } from "@/services/corpus";

export function useDocuments(params: GetDocumentsParams) {
  return useQuery({
    queryKey: ["corpus", "documents", params],
    queryFn: () => getDocuments(params),
    placeholderData: (previousData) => previousData, // keep previous data while fetching
  });
}
