import { useState } from "react"
import { Clapperboard, Loader2, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { ClipEditor } from "@/components/ClipEditor"
import { exportAll, mediaUrl, rateClip } from "@/lib/api"
import { cn, fmtTime } from "@/lib/utils"
import type { Clip, FeedbackRating, ProjectDetail } from "@/lib/types"

const RATING_BTN: Array<{ key: FeedbackRating; icon: typeof ThumbsUp; label: string; active: string }> = [
  { key: "excellent", icon: ThumbsUp, label: "Excelente", active: "bg-emerald-500/25 text-emerald-400 border-emerald-500/40" },
  { key: "good", icon: ThumbsUp, label: "Bom", active: "bg-sky-500/25 text-sky-400 border-sky-500/40" },
  { key: "bad", icon: ThumbsDown, label: "Ruim", active: "bg-amber-500/25 text-amber-400 border-amber-500/40" },
  { key: "ignore", icon: Trash2, label: "Ignorar", active: "bg-red-500/25 text-red-400 border-red-500/40" },
]

function FeedbackRow({ clipId, value, onChanged }: { clipId: string; value: string | null; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null)

  const setRating = async (rating: FeedbackRating) => {
    setBusy(rating)
    try {
      await rateClip(clipId, rating)
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao avaliar")
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="mt-1.5 flex items-center gap-1">
      {RATING_BTN.map((r) => (
        <Button
          key={r.key}
          size="icon-xs"
          variant="ghost"
          className={cn("border", value === r.key ? r.active : "border-transparent text-muted-foreground")}
          title={r.label}
          disabled={busy !== null}
          onClick={() => void setRating(value === r.key ? "none" : r.key)}
        >
          {busy === r.key ? <Loader2 className="animate-spin" /> : <r.icon />}
        </Button>
      ))}
      <span className="ml-auto text-[10px] text-muted-foreground">
        {value ? `⭐ ${value}` : "sem avaliação"}
      </span>
    </div>
  )
}

export function RightPanel({ detail, selectedClipId, currentTime, onSeek, onSelectClip, onChanged, onExportAll }: {
  detail: ProjectDetail
  selectedClipId: string | null
  currentTime: number
  onSeek: (t: number) => void
  onSelectClip: (id: string | null) => void
  onChanged: () => void
  onExportAll: () => void
}) {
  const [exportingAll, setExportingAll] = useState(false)
  const clips = detail.clips ?? []
  const selected = clips.find((c) => c.id === selectedClipId) ?? null

  const handleExportAll = async () => {
    setExportingAll(true)
    try {
      const results = await exportAll(detail.id, clips.map((c) => c.id))
      const ok = results.filter((r) => r.ok).length
      toast.success(`${ok}/${results.length} cortes renderizados`)
      onChanged()
      onExportAll()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao exportar")
    } finally {
      setExportingAll(false)
    }
  }

  return (
    <aside className="flex w-[340px] shrink-0 flex-col border-l border-border bg-background">
      <div className="flex items-center justify-between border-b border-border p-3">
        <span className="text-sm font-semibold">
          Cortes {clips.length > 0 && <span className="text-muted-foreground">({clips.length})</span>}
        </span>
        <div className="flex items-center gap-1">
          {clips.length > 0 && (
            <Button size="xs" variant="outline" onClick={() => void handleExportAll()} disabled={exportingAll}>
              {exportingAll ? <Loader2 className="animate-spin" /> : <Clapperboard />}
              Exportar todos
            </Button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {clips.length === 0 && (
          <div className="mt-10 px-6 text-center text-xs text-muted-foreground">
            {detail.has_transcription
              ? "Os cortes gerados aparecerão aqui após o processamento."
              : "Importe um vídeo e clique em Processar."}
          </div>
        )}

        <div className="space-y-2 p-2">
          {clips.map((clip: Clip) => (
            <div
              key={clip.id}
              className={cn(
                "overflow-hidden rounded-lg border transition-colors",
                selected?.id === clip.id ? "border-primary/60 bg-primary/5" : "border-border bg-card",
              )}
            >
              <button
                type="button"
                className="flex w-full items-center gap-2.5 p-2 text-left"
                onClick={() => onSelectClip(selected?.id === clip.id ? null : clip.id)}
              >
                {clip.files?.thumbnail ? (
                  <img
                    src={mediaUrl(clip.files.thumbnail)}
                    alt=""
                    className="size-12 shrink-0 rounded-md object-cover"
                  />
                ) : (
                  <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-muted text-[9px] text-muted-foreground">
                    9:16
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{clip.title || clip.id}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {fmtTime(clip.duration)} · {Math.round(clip.total_score * 100)}% score
                  </p>
                  {clip.transcript_excerpt && (
                    <p className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground/80">
                      “{clip.transcript_excerpt}”
                    </p>
                  )}
                </div>
              </button>
              <div className="px-2 pb-1">
                <FeedbackRow clipId={clip.id} value={clip.feedback} onChanged={onChanged} />
              </div>
              {selected?.id === clip.id && (
                <ClipEditor
                  detail={detail}
                  clip={clip}
                  currentTime={currentTime}
                  onChanged={onChanged}
                  onSeek={onSeek}
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
