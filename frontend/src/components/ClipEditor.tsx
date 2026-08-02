import { useEffect, useState } from "react"
import {
  Captions,
  Clapperboard,
  Download,
  Loader2,
  Scissors,
  Wand2,
} from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Slider } from "@/components/ui/slider"
import { Textarea } from "@/components/ui/textarea"
import { downloadUrl, editClip, exportClip, regenerateText, splitClip } from "@/lib/api"
import { cn, fmtTime } from "@/lib/utils"
import type { Clip, ProjectDetail } from "@/lib/types"

export function ClipEditor({ detail, clip, currentTime, onChanged, onSeek }: {
  detail: ProjectDetail
  clip: Clip
  currentTime: number
  onChanged: () => void
  onSeek: (t: number) => void
}) {
  const [draft, setDraft] = useState({
    title: clip.title,
    caption: clip.caption,
    description: clip.description,
    hashtags: clip.hashtags.join(", "),
    hook: clip.hook,
    cta: clip.cta,
  })
  const [start, setStart] = useState(clip.source_start)
  const [end, setEnd] = useState(clip.source_end)
  const [exporting, setExporting] = useState(false)
  const [regenerating, setRegenerating] = useState<string | null>(null)

  useEffect(() => {
    setDraft({
      title: clip.title,
      caption: clip.caption,
      description: clip.description,
      hashtags: clip.hashtags.join(", "),
      hook: clip.hook,
      cta: clip.cta,
    })
    setStart(clip.source_start)
    setEnd(clip.source_end)
  }, [clip.id])

  const dirty =
    draft.title !== clip.title ||
    draft.caption !== clip.caption ||
    draft.description !== clip.description ||
    draft.hashtags !== clip.hashtags.join(", ") ||
    draft.hook !== clip.hook ||
    draft.cta !== clip.cta ||
    start !== clip.source_start ||
    end !== clip.source_end

  const save = async () => {
    try {
      await editClip(clip.id, {
        ...draft,
        hashtags: draft.hashtags.split(",").map((h) => h.trim()).filter(Boolean),
        source_start: start,
        source_end: end,
      })
      toast.success("Corte atualizado")
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar")
    }
  }

  const handleSplit = async () => {
    if (!(clip.source_start < currentTime && currentTime < clip.source_end)) {
      toast.error("Mova o playhead para dentro do corte antes de dividir")
      return
    }
    try {
      await splitClip(clip.id, currentTime)
      toast.success("Corte dividido")
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao dividir")
    }
  }

  const handleRegenerate = async (field: "title" | "caption") => {
    setRegenerating(field)
    try {
      const res = await regenerateText(clip.id, field)
      setDraft((d) => ({ ...d, [field]: res[field] ?? d[field] }))
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "IA indisponível")
    } finally {
      setRegenerating(null)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await exportClip(clip.id)
      if (res.ok) {
        onChanged()
        toast.success("Corte renderizado")
      } else {
        toast.error(res.error || "Falha na renderização")
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha na renderização")
    } finally {
      setExporting(false)
    }
  }

  const videoUrl = clip.files?.video ? downloadUrl(clip.files.video) : ""

  return (
    <div className="space-y-3 border-t border-border p-3">
      <div>
        <p className="text-xs font-semibold text-muted-foreground">Editor do corte</p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Input
            value={draft.title}
            onChange={(e) => setDraft((d) => ({ ...d, title: e.target.value }))}
            className="h-7 flex-1 text-sm"
            placeholder="Título"
          />
          <Button
            size="icon-sm"
            variant="outline"
            title="Regenerar título com IA"
            disabled={regenerating === "title"}
            onClick={() => void handleRegenerate("title")}
          >
            {regenerating === "title" ? <Loader2 className="animate-spin" /> : <Wand2 />}
          </Button>
        </div>
        <Textarea
          value={draft.caption}
          onChange={(e) => setDraft((d) => ({ ...d, caption: e.target.value }))}
          className="min-h-20 text-sm"
          placeholder="Legenda da postagem"
        />
        <Input
          value={draft.hashtags}
          onChange={(e) => setDraft((d) => ({ ...d, hashtags: e.target.value }))}
          className="h-7 text-sm"
          placeholder="#hashtags, separadas por vírgula"
        />
      </div>

      <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-2.5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Trecho no vídeo</span>
          <span className="font-mono">
            {fmtTime(start)} — {fmtTime(end)} ({fmtTime(end - start)})
          </span>
        </div>
        <div className="space-y-1">
        <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="w-8 shrink-0">Início</span>
          <Slider
            value={[start]}
            min={0}
            max={detail.duration || end}
            step={0.1}
            onValueChange={(val) => {
              const v = Array.isArray(val) ? val[0] : val
              if (v != null) setStart(Math.min(v, end - 1))
            }}
            className="flex-1"
          />
        </label>
        <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="w-8 shrink-0">Fim</span>
          <Slider
            value={[end]}
            min={0}
            max={detail.duration || end}
            step={0.1}
            onValueChange={(val) => {
              const v = Array.isArray(val) ? val[0] : val
              if (v != null) setEnd(Math.max(v, start + 1))
            }}
            className="flex-1"
          />
        </label>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="xs"
            variant="outline"
            className="flex-1"
            onClick={() => void handleSplit()}
          >
            <Scissors /> Dividir no playhead
          </Button>
          <Button size="xs" variant="outline" onClick={() => onSeek(start)}>
            Ver trecho
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1"
          disabled={!dirty}
          title="Salva os ajustes de texto e do trecho selecionado"
          onClick={() => void save()}
        >
          Salvar alterações
        </Button>
        <Button size="sm" className="flex-1" onClick={() => void handleExport()} disabled={exporting || !dirty && !clip.files?.video && false}>
          {exporting ? <Loader2 className="animate-spin" /> : <Clapperboard />}
          {clip.files?.video ? "Re-renderizar" : "Renderizar 1080x1920"}
        </Button>
        {videoUrl && (
          <a
            href={videoUrl}
            download
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-border px-2.5 text-sm transition-colors hover:bg-muted"
          >
            <Download /> Baixar
          </a>
        )}
        {clip.files?.subtitle && (
          <a
            href={downloadUrl(clip.files.subtitle)}
            download
            className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-border px-2.5 text-sm transition-colors hover:bg-muted"
            title="Baixar legenda .srt do corte"
          >
            <Captions /> .srt
          </a>
        )}
      </div>
      {exporting && <Progress value={40} className="h-1 animate-pulse" />}

      {clip.scores && (
        <>
          <div className="grid grid-cols-3 gap-1.5 text-center">
          {(
            [
              ["Retenção", clip.scores.retention],
              ["Viral", clip.scores.virality],
              ["Emocional", clip.scores.emotion],
              ["Educativo", clip.scores.educational],
              ["Compartilhar", clip.scores.sharing],
              ["Clareza", clip.scores.clarity],
            ] as const
          ).map(([label, v]) => (
            <div key={label} className="rounded-md border border-border bg-muted/40 px-1 py-1.5">
              <p className="text-[10px] text-muted-foreground">{label}</p>
              <p className={cn("text-xs font-semibold", v >= 0.7 ? "text-emerald-400" : v >= 0.4 ? "text-amber-400" : "text-muted-foreground")}>
                {Math.round(v * 100)}%
              </p>
            </div>
          ))}
        </div>
          <p className="text-[10px] text-muted-foreground">
            Estimativa automática do editor de IA para comparar cortes entre si.
          </p>
        </>
      )}
    </div>
  )
}
