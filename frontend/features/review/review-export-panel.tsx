"use client"

import { useReviewStore } from "./review-store"
import { Button } from "@/components/ui/button"
import { Download } from "lucide-react"
import { exportReviewToMarkdown } from "@/services/review"

export function ReviewExportPanel() {
  const { activeReview } = useReviewStore()

  if (!activeReview) return null

  const handleExportMarkdown = () => {
    const md = exportReviewToMarkdown(activeReview)
    const blob = new Blob([md], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `review-${activeReview.request.topic.replace(/\s+/g, '-')}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportJson = () => {
    const json = JSON.stringify(activeReview, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `review-${activeReview.request.topic.replace(/\s+/g, '-')}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-wrap gap-2 mt-4">
      <Button variant="outline" size="sm" onClick={handleExportMarkdown}>
        <Download className="w-4 h-4 mr-2" />
        Export Markdown
      </Button>
      <Button variant="outline" size="sm" onClick={handleExportJson}>
        <Download className="w-4 h-4 mr-2" />
        Export JSON
      </Button>
    </div>
  )
}
