import { useCallback, useRef } from "react"
import { cn, fmtTime } from "@/lib/utils"
import type { Clip, ProjectDetail } from "@/lib/types"

interface TimelineProps {
  detail: ProjectDetail
  currentTime: number
  selectedClipId: string | null
  onSeek: (t: number) => void
}

/**
 * Linha do tempo do vídeo original: energia das frases, cenas,
 * silêncios e faixas dos cortes gerados. Clique para buscar.
 */
export function Timeline({ detail, currentTime, selectedClipId, onSeek }: TimelineProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const duration = detail.duration || 1
  const sentences = detail.transcription?.segments ?? []
  const signals = detail.analysis?.sentence_signals ?? []
  const clips = detail.clips ?? []
  const scenes = detail.analysis?.scenes ?? []
  const silences = detail.analysis?.silences ?? []

  const pos = (t: number) => (t / duration) * 100

  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = barRef.current?.getBoundingClientRect()
    if (!rect) return
    const frac = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1)
    onSeek(frac * duration)
  }, [duration, onSeek])

  const signalFor = (sentenceIndex: number) =>
    signals.find((s) => s.sentence_index === sentenceIndex)

  return (
    <div className="select-none">
      <div
        ref={barRef}
        onClick={handleClick}
        className="relative h-14 w-full cursor-crosshair overflow-hidden rounded-lg border border-border bg-card"
        title="Clique para navegar"
      >
        {/* energia das frases */}
        <div className="absolute inset-x-0 top-0 flex h-8 items-end gap-px px-px">
          {sentences.map((s) => {
            const sig = signalFor(s.id)
            const h = Math.max(6, Math.round((sig?.energy ?? 0.35) * 100))
            return (
              <div
                key={s.id}
                className="flex-1 rounded-t-sm bg-primary/40"
                style={{ height: `${h}%` }}
              />
            )
          })}
        </div>
        {/* silêncios */}
        <div className="absolute inset-x-0 top-0 h-8">
          {silences.map((s, i) => (
            <div
              key={i}
              className="absolute h-full bg-red-500/25"
              style={{ left: `${pos(s.start)}%`, width: `${pos(s.end) - pos(s.start)}%` }}
            />
          ))}
        </div>
        {/* cenas */}
        <div className="absolute inset-x-0 top-8 flex h-2">
          {scenes.map((s, i) => (
            <div
              key={i}
              className="flex-1 border-r border-background bg-sky-500/40"
              style={{ width: `${pos(s.end) - pos(s.start)}%` }}
            />
          ))}
        </div>
        {/* faixas dos cortes */}
        <div className="absolute inset-x-0 top-[38px] flex h-4 gap-px">
          {clips.map((c) => (
            <div
              key={c.id}
              onClick={(e) => { e.stopPropagation(); onSeek(c.source_start) }}
              title={`${c.title} — ${fmtTime(c.duration)}`}
              className={cn(
                "rounded-sm border border-background",
                selectedClipId === c.id
                  ? "bg-primary"
                  : "bg-emerald-500/70 hover:bg-emerald-400",
              )}
              style={{ width: `${pos(c.source_end) - pos(c.source_start)}%` }}
            />
          ))}
        </div>
        {/* playhead */}
        <div
          className="pointer-events-none absolute inset-y-0 w-px bg-white shadow-[0_0_4px_rgba(0,0,0,0.8)]"
          style={{ left: `${pos(currentTime)}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>{fmtTime(0)}</span>
        <span>{fmtTime(duration)}</span>
      </div>
    </div>
  )
}

export type { Clip }
