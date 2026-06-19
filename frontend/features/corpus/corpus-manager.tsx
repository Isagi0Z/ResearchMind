"use client"

import { useState, useEffect, useRef } from "react"
import { useCorpusStore } from "./corpus-store"
import { useDocuments } from "./use-corpus-data"
import { JobProgressPanel } from "@/features/jobs/job-progress-panel"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Search, Download, Plus, RefreshCw, SlidersHorizontal } from "lucide-react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { StatusBadge } from "@/components/shared/status-badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ErrorState } from "@/components/shared/error-state"
import { EmptyState } from "@/components/shared/empty-state"
import { useVirtualizer } from "@tanstack/react-virtual"
import { Sheet, SheetContent, SheetTrigger, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet"
import { FiltersPanel } from "./filters-panel"

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delay])

  return debouncedValue
}

export function CorpusManager() {
  const { 
    searchQuery, setSearchQuery, 
    filters, sort, pagination,
    selectedRows, toggleRowSelection
  } = useCorpusStore()
  
  const [localSearch, setLocalSearch] = useState(searchQuery)
  const debouncedSearch = useDebounce(localSearch, 500)
  const [isFiltersOpen, setIsFiltersOpen] = useState(false)
  const [processingJobId, setProcessingJobId] = useState<string | null>(null)

  // Sync debounced search to store
  useEffect(() => {
    if (debouncedSearch !== searchQuery) {
      setSearchQuery(debouncedSearch)
    }
  }, [debouncedSearch, searchQuery, setSearchQuery])

  const { data, isLoading, isError, refetch } = useDocuments({
    pageIndex: pagination.pageIndex,
    pageSize: pagination.pageSize, // Using 1000 for full virtualization
    searchQuery: debouncedSearch,
    sortBy: sort.column,
    sortDirection: sort.direction,
    filters
  })

  // Virtualization Setup
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const rows = data?.data || []
  
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 53, // Approximate row height
    overscan: 10,
  })

  const virtualItems = virtualizer.getVirtualItems()

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Corpus Manager</h1>
          <p className="text-muted-foreground mt-1">
            Manage and explore your ingested research documents.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline" size="sm">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button size="sm">
            <Plus className="w-4 h-4 mr-2" />
            Add Document
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents by title or author..."
            className="pl-8"
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
          />
        </div>
        <Sheet open={isFiltersOpen} onOpenChange={setIsFiltersOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" className="shrink-0">
              <SlidersHorizontal className="w-4 h-4 mr-2" />
              Filters
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full sm:max-w-md p-0 flex flex-col">
             <SheetHeader className="p-6 pb-2 text-left">
               <SheetTitle>Filter Documents</SheetTitle>
               <SheetDescription>Narrow down your corpus by year, author, and status.</SheetDescription>
             </SheetHeader>
             <FiltersPanel onClose={() => setIsFiltersOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>

      <JobProgressPanel jobId={processingJobId} />

      <div className="border rounded-md bg-card flex-1 flex flex-col overflow-hidden min-h-[500px]">
        {isError ? (
          <div className="flex-1 flex items-center justify-center">
             <ErrorState title="Failed to load documents" onRetry={refetch} />
          </div>
        ) : isLoading && !data ? (
          <div className="p-4 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                <Skeleton className="h-6 w-6" />
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-6 w-1/4" />
                <Skeleton className="h-6 w-16" />
              </div>
            ))}
          </div>
        ) : !data || rows.length === 0 ? (
          <div className="flex-1 flex items-center justify-center">
            <EmptyState 
              title="No documents found" 
              description="Try adjusting your search query or filters."
              icon={<Search className="w-10 h-10" />}
            />
          </div>
        ) : (
          <>
            <div className="overflow-auto flex-1" ref={scrollContainerRef}>
              <Table>
                <TableHeader className="sticky top-0 bg-card z-10 shadow-sm">
                  <TableRow>
                    <TableHead className="w-12 text-center">
                       <input 
                          type="checkbox" 
                          className="rounded border-muted-foreground" 
                          checked={rows.length > 0 && rows.every(d => selectedRows[d.ruo_id])}
                          onChange={() => {
                            const allSelected = rows.every(d => selectedRows[d.ruo_id])
                            const newSelection = { ...selectedRows }
                            rows.forEach(d => {
                              if (allSelected) delete newSelection[d.ruo_id]
                              else newSelection[d.ruo_id] = true
                            })
                           useCorpusStore.getState().setSelectedRows(newSelection)
                         }}
                       />
                    </TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead className="hidden md:table-cell">Authors</TableHead>
                    <TableHead className="w-24 text-center">Year</TableHead>
                    <TableHead className="w-24 text-center">Entities</TableHead>
                    <TableHead className="w-32">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {virtualItems.length > 0 && (
                    <TableRow style={{ height: `${virtualItems[0]?.start ?? 0}px` }} className="hover:bg-transparent border-0 pointer-events-none">
                      <TableCell colSpan={6} className="p-0" />
                    </TableRow>
                  )}
                  {virtualItems.map((virtualRow) => {
                    const doc = rows[virtualRow.index]
                    const authors = doc.authors ? doc.authors.join(", ") : ""
                    
                    return (
                      <TableRow 
                        key={doc.ruo_id} 
                        className="hover:bg-muted/50 cursor-pointer"
                        data-index={virtualRow.index}
                        ref={virtualizer.measureElement}
                      >
                        <TableCell className="text-center" onClick={(e) => e.stopPropagation()}>
                          <input 
                            type="checkbox" 
                            className="rounded border-muted-foreground" 
                            checked={!!selectedRows[doc.ruo_id]}
                            onChange={() => toggleRowSelection(doc.ruo_id)}
                          />
                        </TableCell>
                        <TableCell className="font-medium max-w-[300px] truncate" title={doc.title}>
                          {doc.title}
                        </TableCell>
                        <TableCell className="hidden md:table-cell max-w-[200px] truncate text-muted-foreground" title={authors}>
                          {authors}
                        </TableCell>
                        <TableCell className="text-center text-muted-foreground">
                          {doc.year ?? "-"}
                        </TableCell>
                        <TableCell className="text-center text-muted-foreground">
                          {doc.entity_count}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={doc.status as any} />
                        </TableCell>
                      </TableRow>
                    )
                  })}
                  {virtualItems.length > 0 && (
                    <TableRow style={{ height: `${virtualizer.getTotalSize() - (virtualItems[virtualItems.length - 1]?.end ?? 0)}px` }} className="hover:bg-transparent border-0 pointer-events-none">
                      <TableCell colSpan={6} className="p-0" />
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
            
            <div className="flex items-center justify-between border-t p-4 bg-card">
              <div className="text-sm text-muted-foreground">
                Showing {data.total} entries
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
