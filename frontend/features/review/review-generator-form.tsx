"use client"

import { useReviewStore } from "./review-store"
import { ReviewType } from "@/types/review"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { generateReview } from "@/services/review"

// CRC32 helper
function crc32(str: string): string {
  let crc = 0 ^ (-1);
  for (let i = 0; i < str.length; i++) {
    let byte = str.charCodeAt(i);
    crc = crc ^ byte;
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
    }
  }
  return ((crc ^ (-1)) >>> 0).toString(16).padStart(8, '0');
}

const REVIEW_TYPES: { type: ReviewType, desc: string }[] = [
  { type: 'GENERAL', desc: 'Comprehensive thematic overview' },
  { type: 'METHOD', desc: 'Analysis of applied techniques' },
  { type: 'DATASET', desc: 'Corpus integrity and scope' },
  { type: 'CONSENSUS', desc: 'High agreement synthesis' },
  { type: 'CONTRADICTION', desc: 'Divergent findings and debates' },
  { type: 'RESEARCH_GAP', desc: 'Unexplored research nodes' },
  { type: 'COMPARATIVE', desc: 'A/B matrix analysis' },
  { type: 'LANDSCAPE', desc: 'Macro broad trends evolution' },
]

export function ReviewGeneratorForm() {
  const { reviewConfig, setReviewConfig, setGenerationStage, setActiveReview } = useReviewStore()

  const handleGenerate = async () => {
    if (!reviewConfig.topic) return

    setActiveReview(null)
    
    // Trigger the deterministic 7-stage pipeline mock
    const stages = [
      'theme_detection',
      'evidence_collection',
      'finding_generation',
      'section_building',
      'traceability_verification',
      'confidence_computation',
      'final_assembly'
    ] as const

    for (const stage of stages) {
      setGenerationStage(stage)
      await new Promise(r => setTimeout(r, 600)) // 600ms per stage for UX simulation
    }

    const request = {
      id: crc32(reviewConfig.topic + reviewConfig.type),
      topic: reviewConfig.topic,
      type: reviewConfig.type || 'GENERAL',
      targetEntities: reviewConfig.targetEntities || [],
      documentScope: reviewConfig.documentScope || 'all'
    }

    try {
      const result = await generateReview(request)
      setActiveReview(result)
      setGenerationStage('completed')
    } catch (error) {
      console.error(error)
      setGenerationStage('failed')
    }
  }

  return (
    <Card className="max-w-3xl mx-auto mt-8">
      <CardHeader>
        <CardTitle>Configure Systematic Review</CardTitle>
        <CardDescription>Define parameters for the M6 Synthesis Engine.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        
        <div className="space-y-2">
          <Label htmlFor="topic">Research Topic</Label>
          <Input 
            id="topic"
            placeholder="Enter research topic or core question..."
            value={reviewConfig.topic}
            onChange={e => setReviewConfig({ topic: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label>Review Type</Label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {REVIEW_TYPES.map((rt) => (
              <Button
                key={rt.type}
                variant={reviewConfig.type === rt.type ? "default" : "outline"}
                className="h-auto py-2 flex-col items-start text-left gap-1"
                onClick={() => setReviewConfig({ type: rt.type })}
              >
                <div className="text-sm font-semibold">{rt.type}</div>
                <div className="text-[10px] text-muted-foreground truncate w-full">{rt.desc}</div>
              </Button>
            ))}
          </div>
        </div>

        <div className="pt-4 flex justify-end">
          <Button onClick={handleGenerate} disabled={!reviewConfig.topic}>
            Synthesize Review
          </Button>
        </div>

      </CardContent>
    </Card>
  )
}
