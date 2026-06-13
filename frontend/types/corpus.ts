import { DocumentType, StageStatus } from "./enums";

export interface CorpusFilters {
  yearRange: [number, number];
  authors: string[];
  source: string[];
  status: StageStatus[];
}

export interface SortConfig {
  column: string;
  direction: "asc" | "desc";
}

export interface PaginationState {
  pageIndex: number;
  pageSize: number;
}
