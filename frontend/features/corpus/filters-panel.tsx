"use client"

import { useCorpusStore } from "./corpus-store"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Checkbox } from "@/components/ui/checkbox"
import { useState } from "react"
import { StageStatus } from "@/types/enums"
import { X } from "lucide-react"

const SOURCES = ["Journal", "Conference", "ArXiv", "Other"]
const STATUSES: { value: StageStatus, label: string }[] = [
  { value: "success", label: "Processed" },
  { value: "partial", label: "Pending" },
  { value: "failed", label: "Failed" }
]

export function FiltersPanel({ onClose }: { onClose?: () => void }) {
  const { filters, setFilters, clearFilters } = useCorpusStore()
  
  const [minYear, setMinYear] = useState<string>(filters.yearRange[0].toString())
  const [maxYear, setMaxYear] = useState<string>(filters.yearRange[1].toString())
  const [authorInput, setAuthorInput] = useState("")

  const handleApply = () => {
    setFilters({
      yearRange: [parseInt(minYear) || 2000, parseInt(maxYear) || 2026]
    })
    if (onClose) onClose()
  }

  const handleAddAuthor = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && authorInput.trim()) {
      e.preventDefault()
      if (!filters.authors.includes(authorInput.trim())) {
        setFilters({ authors: [...filters.authors, authorInput.trim()] })
      }
      setAuthorInput("")
    }
  }

  const handleRemoveAuthor = (author: string) => {
    setFilters({ authors: filters.authors.filter(a => a !== author) })
  }

  const handleToggleSource = (source: string) => {
    const newSources = filters.source.includes(source)
      ? filters.source.filter(s => s !== source)
      : [...filters.source, source]
    setFilters({ source: newSources })
  }

  const handleToggleStatus = (status: StageStatus) => {
    const newStatuses = filters.status.includes(status)
      ? filters.status.filter(s => s !== status)
      : [...filters.status, status]
    setFilters({ status: newStatuses })
  }

  const handleClear = () => {
    clearFilters()
    setMinYear("2000")
    setMaxYear("2026")
    setAuthorInput("")
  }

  return (
    <div className="flex flex-col h-full bg-card">
      <ScrollArea className="flex-1 p-6">
        <div className="space-y-6">
          
          <div className="space-y-3">
            <Label>Year Range</Label>
            <div className="flex items-center gap-2">
              <Input 
                type="number" 
                value={minYear} 
                onChange={(e) => setMinYear(e.target.value)}
                placeholder="Min" 
              />
              <span className="text-muted-foreground">-</span>
              <Input 
                type="number" 
                value={maxYear} 
                onChange={(e) => setMaxYear(e.target.value)}
                placeholder="Max" 
              />
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <Label>Authors</Label>
            <Input 
              placeholder="Type and press Enter..." 
              value={authorInput}
              onChange={(e) => setAuthorInput(e.target.value)}
              onKeyDown={handleAddAuthor}
            />
            {filters.authors.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {filters.authors.map(author => (
                  <Badge key={author} variant="secondary" className="gap-1 pr-1">
                    {author}
                    <div 
                      role="button"
                      tabIndex={0}
                      className="cursor-pointer rounded-full p-0.5 hover:bg-muted"
                      onClick={() => handleRemoveAuthor(author)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleRemoveAuthor(author) }}
                    >
                      <X className="w-3 h-3" />
                    </div>
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <Separator />

          <div className="space-y-3">
            <Label>Status</Label>
            <div className="space-y-2">
              {STATUSES.map(status => (
                <div key={status.value} className="flex items-center space-x-2">
                  <Checkbox 
                    id={`status-${status.value}`} 
                    checked={filters.status.includes(status.value)}
                    onCheckedChange={() => handleToggleStatus(status.value)}
                  />
                  <label 
                    htmlFor={`status-${status.value}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {status.label}
                  </label>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          <div className="space-y-3">
            <Label>Source / Venue</Label>
            <div className="space-y-2">
              {SOURCES.map(source => (
                <div key={source} className="flex items-center space-x-2">
                  <Checkbox 
                    id={`source-${source}`} 
                    checked={filters.source.includes(source)}
                    onCheckedChange={() => handleToggleSource(source)}
                  />
                  <label 
                    htmlFor={`source-${source}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {source}
                  </label>
                </div>
              ))}
            </div>
          </div>

        </div>
      </ScrollArea>

      <div className="p-6 border-t flex flex-col gap-2 mt-auto bg-card">
        <Button onClick={handleApply} className="w-full">
          Apply Filters
        </Button>
        <Button variant="outline" onClick={handleClear} className="w-full">
          Clear Filters
        </Button>
      </div>
    </div>
  )
}
