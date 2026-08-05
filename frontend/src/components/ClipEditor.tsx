import { useEffect, useState } from "react"
import {
  Captions,
  Clapperboard,
  Download,
  LayoutTemplate,
  Loader2,
  Play,
  Scissors,
  Type,
  Wand2,
} from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Slider } from "@/components/ui/slider"
import { Textarea } from "@/components/ui/textarea"
import { TemplateGallery } from "@/components/TemplateGallery"
import { downloadUrl, editClip, exportClip, previewClip, regenerateText, splitClip } from "@/lib/api"
import { cn, fmtTime } from "@/lib/utils"
import type { Clip, ProjectDetail, Template } from "@/lib/types"

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
  const [tplOpen, setTplOpen] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [previewUrl, setPreviewUrl] = useState("")
  const [subStyle, setSubStyle] = useState<Record<string, unknown>>(
    clip.subtitle_style ?? { style: "tiktok", position: "bottom", words_per_line: 6, animation: "pop" }
  )

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
    setSubStyle(clip.subtitle_style ?? { style: "tiktok", position: "bottom", words_per_line: 6, animation: "pop" })
    setPreviewUrl("")
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

  const applyTemplate = async (t: Template) => {
    try {
      await editClip(clip.id, { template_id: t.id })
      toast.success(`Template "${t.name}" aplicado`)
      setTplOpen(false)
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao aplicar template")
    }
  }

  const clearTemplate = async () => {
    try {
      await editClip(clip.id, { template_id: "" })
      toast.success("Template removido")
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao remover template")
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

  const handleExport = async (force = false) => {
    setExporting(true)
    try {
      const res = await exportClip(clip.id, force)
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

  const handlePreview = async () => {
    setPreviewing(true)
    try {
      const res = await previewClip(clip.id)
      if (res.ok) {
        setPreviewUrl(downloadUrl(res.path))
        toast.success("Prévia gerada")
      } else {
        toast.error(res.error || "Falha ao gerar prévia")
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha na prévia")
    } finally {
      setPreviewing(false)
    }
  }

  const saveSubtitleStyle = (patch: Record<string, unknown>) => {
    const next = { ...subStyle, ...patch }
    setSubStyle(next)
    void editClip(clip.id, { subtitle_style: next })
      .then(() => {
        toast.success("Estilo de legenda salvo")
        onChanged()
      })
      .catch((e) => toast.error(e instanceof Error ? e.message : "Falha ao salvar estilo"))
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
          onClick={() => setTplOpen(true)}
          className={clip.template_id ? "shrink-0 border-emerald-500/50 text-emerald-500" : "shrink-0"}
          title={clip.template_id ? "Template aplicado — clique para trocar" : "Escolher um template visual"}
        >
          <LayoutTemplate /> Template
        </Button>
        {clip.template_id && (
          <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" onClick={() => void clearTemplate()}>
            remover
          </Button>
        )}
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
        <Button size="sm" className="flex-1" onClick={() => void handleExport(!!clip.files?.video)} disabled={exporting || !dirty && !clip.files?.video && false}>
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

      <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-2.5">
        <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
          <Type className="h-3.5 w-3.5" /> Estilo das legendas do corte
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="space-y-1 text-[11px] text-muted-foreground">
            <span>Estilo</span>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
              value={String(subStyle.style ?? "tiktok")}
              onChange={(e) => saveSubtitleStyle({ style: e.target.value })}
            >
              <option value="tiktok">TikTok</option>
              <option value="instagram">Instagram</option>
              <option value="word_by_word">Palavra por palavra</option>
              <option value="karaoke">Karaokê</option>
              <option value="minimal">Minimalista</option>
            </select>
          </label>
          <label className="space-y-1 text-[11px] text-muted-foreground">
            <span>Posição</span>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
              value={String(subStyle.position ?? "bottom")}
              onChange={(e) => saveSubtitleStyle({ position: e.target.value })}
            >
              <option value="bottom">Inferior</option>
              <option value="middle">Meio</option>
              <option value="top">Superior</option>
            </select>
          </label>
          <label className="space-y-1 text-[11px] text-muted-foreground">
            <span>Animação</span>
            <select
              className="w-full rounded-md border border-border bg-background px-2 py-1 text-xs"
              value={String(subStyle.animation ?? "pop")}
              onChange={(e) => saveSubtitleStyle({ animation: e.target.value })}
            >
              <option value="pop">Pop</option>
              <option value="slide">Deslizar</option>
              <option value="slide_up">Subir</option>
              <option value="fade">Fade</option>
              <option value="fade_up">Fade + subir</option>
            </select>
          </label>
          <label className="space-y-1 text-[11px] text-muted-foreground">
            <span>Palavras por linha: {String(subStyle.words_per_line ?? 6)}</span>
            <Slider
              value={[Number(subStyle.words_per_line ?? 6)]}
              min={2}
              max={10}
              step={1}
              onValueChange={(val) => saveSubtitleStyle({ words_per_line: Array.isArray(val) ? val[0] : val })}
            />
          </label>
        </div>
      </div>

      <div className="space-y-2">
        <Button size="sm" variant="outline" className="w-full" onClick={() => void handlePreview()} disabled={previewing}>
          {previewing ? <Loader2 className="animate-spin" /> : <Play />}
          Pré-visualizar corte (rápido, 540x960)
        </Button>
        {previewUrl && (
          <video src={previewUrl} controls playsInline className="w-full rounded-lg border border-border bg-black" />
        )}
      </div>

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

      <TemplateGallery
        open={tplOpen}
        onOpenChange={setTplOpen}
        onSelect={(t) => void applyTemplate(t)}
        currentId={clip.template_id}
      />
    </div>
  )
}
