import { useEffect, useRef, useState } from "react"
import { Captions, Download, Loader2, Pause, Play, SkipBack, SkipForward } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Timeline } from "@/components/Timeline"
import { generateSubtitles, mediaUrl } from "@/lib/api"
import { cn, fmtTime } from "@/lib/utils"
import type { ProjectDetail } from "@/lib/types"

const STEP_IDS = ["audio", "transcription", "signals", "content", "clips", "metadata", "render"]

function StepsPanel({ detail }: { detail: ProjectDetail }) {
  const anyRunning = detail.steps.some((s) => s.status === "running")

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold">Processando vídeo</span>
        <span className="text-xs text-muted-foreground">{Math.round(detail.progress * 100)}%</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4 lg:grid-cols-7">
        {STEP_IDS.map((id) => {
          const step = detail.steps.find((s) => s.id === id)
          if (!step) return null
          return (
            <div key={id} className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "size-2 shrink-0 rounded-full",
                    step.status === "done" && "bg-emerald-500",
                    step.status === "running" && "animate-pulse bg-sky-500",
                    step.status === "error" && "bg-red-500",
                    step.status === "pending" && "bg-muted-foreground/40",
                  )}
                />
                <span className="truncate text-xs font-medium">{step.label}</span>
              </div>
              <Progress
                value={(step.status === "done" ? 100 : step.progress) * 100}
                className="mt-1 h-1"
              />
              {step.detail && step.status !== "pending" && (
                <p className="mt-0.5 truncate text-[10px] text-muted-foreground">{step.detail}</p>
              )}
            </div>
          )
        })}
      </div>
      {!anyRunning && detail.status === "processing" && (
        <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" /> Aguardando na fila…
        </p>
      )}
    </div>
  )
}

function VideoPlayer({ src, currentTime, onTimeUpdate }: {
  src: string
  currentTime: number
  onTimeUpdate: (t: number) => void
}) {
  const ref = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState(false)
  const [pct, setPct] = useState(0)
  const [dur, setDur] = useState(0)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    setLoaded(false)
    setPlaying(false)
    setPct(0)
    setDur(0)
  }, [src])

  useEffect(() => {
    const v = ref.current
    if (!v) return
    if (Math.abs(v.currentTime - currentTime) > 1.2 && v.readyState >= 1) {
      v.currentTime = currentTime
    }
  }, [currentTime])

  const toggle = () => {
    const v = ref.current
    if (!v) return
    if (v.paused) void v.play()
    else v.pause()
  }

  return (
    <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-border bg-black">
      <video
        ref={ref}
        src={src}
        className="max-h-full w-full"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={() => {
          const v = ref.current
          if (!v) return
          setPct(v.duration ? v.currentTime / v.duration : 0)
          setDur(v.duration)
          onTimeUpdate(v.currentTime)
        }}
        onLoadedMetadata={() => setLoaded(true)}
        onClick={toggle}
      />
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
          <Loader2 className="size-6 animate-spin" />
        </div>
      )}
      <div className="absolute bottom-2 left-2 rounded bg-black/60 px-1.5 py-0.5 text-[11px] tabular-nums text-white">
        {fmtTime(dur * pct)} / {fmtTime(dur)}
      </div>
      <div className="absolute inset-x-0 bottom-0 flex items-center gap-1 bg-gradient-to-t from-black/70 to-transparent p-2 pt-6">
        <Button size="icon-xs" variant="ghost" className="text-white" onClick={toggle}>
          {playing ? <Pause /> : <Play />}
        </Button>
        <div
          className="relative h-1 flex-1 cursor-pointer rounded-full bg-white/25"
          onClick={(e) => {
            const v = ref.current
            if (!v?.duration) return
            const rect = e.currentTarget.getBoundingClientRect()
            v.currentTime = ((e.clientX - rect.left) / rect.width) * v.duration
          }}
        >
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-white"
            style={{ width: `${pct * 100}%` }}
          />
        </div>
      </div>
    </div>
  )
}

function SubtitlePanel({ detail }: { detail: ProjectDetail }) {
  const [files, setFiles] = useState<Record<string, string> | null>(null)
  const [busy, setBusy] = useState(false)

  const gen = async () => {
    setBusy(true)
    try {
      const res = await generateSubtitles(detail.id)
      setFiles(res.files)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao gerar legendas")
    } finally {
      setBusy(false)
    }
  }

  const has = files

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="xs" variant="outline" onClick={() => void gen()} disabled={busy}>
        {busy ? <Loader2 className="animate-spin" /> : <Captions />}
        {files ? "Regenerar legendas" : "Gerar legendas"}
      </Button>
      {has && (
        <>
          <span className="text-[11px] text-muted-foreground">Baixar:</span>
          {["srt", "vtt", "txt"].map((f) =>
            files[f] ? (
              <a
                key={f}
                href={mediaUrl(files[f])}
                download
                className="inline-flex h-7 items-center gap-1 rounded-md border border-border px-2 text-[11px] transition-colors hover:bg-muted"
              >
                <Download className="size-3" /> .{f}
              </a>
            ) : null,
          )}
        </>
      )}
    </div>
  )
}

export function CenterPanel({ detail, currentTime, selectedClipId, onSeek, onTimeUpdate, videoUrl }: {
  detail: ProjectDetail
  currentTime: number
  selectedClipId: string | null
  onSeek: (t: number) => void
  onTimeUpdate: (t: number) => void
  videoUrl: string
}) {
  return (
    <main className="flex min-w-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
      {detail.status === "processing" && <StepsPanel detail={detail} />}

      {videoUrl && (
        <VideoPlayer src={videoUrl} currentTime={currentTime} onTimeUpdate={onTimeUpdate} />
      )}

      {videoUrl && detail.has_transcription && (
        <Timeline
          detail={detail}
          currentTime={currentTime}
          selectedClipId={selectedClipId}
          onSeek={onSeek}
        />
      )}

      {detail.status === "error" && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
          <p className="font-semibold">Erro no processamento</p>
          <p className="mt-1 text-xs">{detail.error}</p>
          <Button variant="outline" size="sm" className="mt-3"
            onClick={() => window.dispatchEvent(new CustomEvent("process-project", { detail: detail.id }))}>
            Tentar novamente
          </Button>
        </div>
      )}

      {detail.has_transcription && (
        <div className="rounded-lg border border-border bg-card p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-semibold text-muted-foreground">
              {detail.content?.summary ? "Resumo do conteúdo" : "Transcrição"}
            </p>
            <SubtitlePanel detail={detail} />
          </div>
          {detail.content?.summary && (
            <p className="mb-3 text-sm text-foreground/90">{detail.content.summary}</p>
          )}
          {detail.content && detail.content.themes.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {detail.content.themes.map((t) => (
                <span key={t} className="rounded-full border border-border bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                  {t}
                </span>
              ))}
            </div>
          )}
          <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {detail.transcription?.segments.map((seg) => (
              <button
                key={seg.id}
                type="button"
                className={cn(
                  "block w-full rounded px-2 py-1 text-left text-xs transition-colors hover:bg-muted",
                  seg.start <= currentTime && currentTime < seg.end
                    ? "bg-primary/15 text-foreground"
                    : "text-foreground/80",
                )}
                onClick={() => onSeek(seg.start)}
              >
                <span className="mr-2 font-mono text-[10px] text-muted-foreground">
                  {fmtTime(seg.start)}
                </span>
                {seg.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {!detail.has_transcription && detail.status === "ready" && (
        <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <p className="text-sm text-muted-foreground">
            Vídeo importado. Clique em <b>Processar</b> para gerar cortes com legendas.
          </p>
        </div>
      )}

      {detail.status === "created" && (
        <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
          <SkipBack className="size-4" /> Selecione um projeto à esquerda para começar
          <SkipForward className="size-4" />
        </div>
      )}
    </main>
  )
}
