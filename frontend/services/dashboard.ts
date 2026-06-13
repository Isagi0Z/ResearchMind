import { MOCK_DOCUMENTS, MOCK_CORPUS_SUMMARY, MOCK_SYSTEM_STATUS, MOCK_RECENT_REVIEWS } from "./mock-data";

export async function getCorpusSummary() {
  // Simulate network delay
  await new Promise(resolve => setTimeout(resolve, 300));
  return MOCK_CORPUS_SUMMARY;
}

export async function getRecentDocuments() {
  await new Promise(resolve => setTimeout(resolve, 400));
  // Sort by date descending
  return [...MOCK_DOCUMENTS]
    .sort((a, b) => new Date(b.meta.created_at).getTime() - new Date(a.meta.created_at).getTime())
    .slice(0, 10);
}

export async function getSystemStatus() {
  await new Promise(resolve => setTimeout(resolve, 200));
  return MOCK_SYSTEM_STATUS;
}

export async function getRecentReviews() {
  await new Promise(resolve => setTimeout(resolve, 350));
  return MOCK_RECENT_REVIEWS;
}
