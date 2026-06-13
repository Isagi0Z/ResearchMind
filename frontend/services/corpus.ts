import { MOCK_DOCUMENTS } from "./mock-data";
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
  pageIndex: number;
  pageSize: number;
  pageCount: number;
}

export async function getDocuments(params: GetDocumentsParams): Promise<PaginatedResponse<RUODocument>> {
  await new Promise(resolve => setTimeout(resolve, 300)); // Network delay

  let filtered = [...MOCK_DOCUMENTS];

  // Search
  if (params.searchQuery) {
    const q = params.searchQuery.toLowerCase();
    filtered = filtered.filter(doc => 
      doc.header.title.toLowerCase().includes(q) ||
      doc.header.authors.some(a => a.full_name.toLowerCase().includes(q))
    );
  }

  // Filters
  if (params.filters) {
    if (params.filters.yearRange) {
      const [min, max] = params.filters.yearRange;
      filtered = filtered.filter(doc => {
        if (!doc.header.publication_date) return false;
        const year = parseInt(doc.header.publication_date.split('-')[0]);
        return year >= min && year <= max;
      });
    }
    if (params.filters.authors && params.filters.authors.length > 0) {
      const authorSet = new Set(params.filters.authors.map(a => a.toLowerCase()));
      filtered = filtered.filter(doc => 
        doc.header.authors.some(a => authorSet.has(a.full_name.toLowerCase()))
      );
    }
    if (params.filters.source && params.filters.source.length > 0) {
      const sourceSet = new Set(params.filters.source.map(s => s.toLowerCase()));
      filtered = filtered.filter(doc => 
        doc.header.venue && sourceSet.has(doc.header.venue.toLowerCase())
      );
    }
    if (params.filters.status && params.filters.status.length > 0) {
      const statusSet = new Set(params.filters.status);
      filtered = filtered.filter(doc => {
        const finalStatus = doc.meta.pipeline_stages[doc.meta.pipeline_stages.length - 1];
        return statusSet.has(finalStatus);
      });
    }
  }

  // Sorting
  if (params.sortBy) {
    const { sortBy, sortDirection } = params;
    filtered.sort((a, b) => {
      let valA: any = "";
      let valB: any = "";
      
      switch (sortBy) {
        case "title":
          valA = a.header.title;
          valB = b.header.title;
          break;
        case "year":
          valA = a.header.publication_date || "";
          valB = b.header.publication_date || "";
          break;
        case "status":
          valA = a.meta.pipeline_stages[a.meta.pipeline_stages.length - 1];
          valB = b.meta.pipeline_stages[b.meta.pipeline_stages.length - 1];
          break;
        case "entities":
          valA = a.entities.length;
          valB = b.entities.length;
          break;
      }
      
      if (valA < valB) return sortDirection === "asc" ? -1 : 1;
      if (valA > valB) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }

  // Pagination
  const total = filtered.length;
  const pageCount = Math.ceil(total / params.pageSize);
  const start = params.pageIndex * params.pageSize;
  const data = filtered.slice(start, start + params.pageSize);

  return {
    data,
    total,
    pageIndex: params.pageIndex,
    pageSize: params.pageSize,
    pageCount
  };
}
