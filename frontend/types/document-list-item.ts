export interface DocumentListItem {
  ruo_id: string;
  title: string;
  authors: string[];
  year: number | null;
  status: string;
  entity_count: number;
  source: string | null;
}
