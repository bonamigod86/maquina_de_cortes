import { useCallback, useEffect, useRef, useState } from "react"
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Copy,
  Image as ImageIcon,
  LayoutTemplate,
  Loader2,
  Play,
  Rows3,
  Square,
  Trash2,
  Type,
  Video,
} from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import {
  createTemplate,
  getTemplate,
  mediaUrl,
  previewTemplate,
  updateTemplate,
} from "@/lib/api"
import type { Template, TemplateElement } from "@/lib/types"

const CANVAS_W = 400
const CANVAS_H = CANVAS_W * (16 / 9)
const MIN_SIZE = 0.04
const SCALE = CANVAS_W / 1080

const CATEGORIES = ["geral", "podcast", "viral", "news", "gaming", "minimal"]

type EPos = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw"
type El = TemplateElement

interface EditorState {
  name: string
  category: string
  description: string
  background: Record<string, unknown>
  elements: El[]
  subtitle_style_override: Record<string, unknown> | null
}

interface DragState {
  mode: "move" | "resize"
  handle: EPos
  id: string
  startX: number
  startY: number
  orig: { x: number; y: number; w: number; h: number }
  Wpx: number
  Hpx: number
}

function clamp(v: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, v))
}

function newId(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}`
}

function makeElement(type: El["type"]): El {
  const id = newId(type === "shape" ? "s" : type === "text" ? "t" : type === "video_slot" ? "vs" : "e")
  switch (type) {
    case "text":
      return { id, type, x: 0.1, y: 0.1, w: 0.8, h: 0.1, content: "Texto", style: { font_size: 72, color: "#FFFFFF", align: "center", weight: 700 } }
    case "shape":
      return { id, type, x: 0.05, y: 0.05, w: 0.9, h: 0.12, content: null, style: { shape: "rect", color: "#DC2626", opacity: 1, outline: 0 } }
    case "video_slot":
      return { id, type, x: 0.05, y: 0.16, w: 0.9, h: 0.55, content: null, style: {} }
    case "image":
    case "logo":
      return { id, type, x: 0.35, y: 0.05, w: 0.3, h: 0.15, content: "", style: {} }
    case "cover":
      return { id, type, x: 0.05, y: 0.05, w: 0.9, h: 0.9, content: null, style: { color: "#000000", opacity: 0.4 } }
    case "subtitle_area":
      return { id, type, x: 0.05, y: 0.78, w: 0.9, h: 0.16, content: null, style: {} }
  }
}

const ELEMENT_LABEL: Record<El["type"], string> = {
  text: "Texto",
  shape: "Forma",
  video_slot: "Vídeo",
  image: "Imagem",
  logo: "Logo",
  cover: "Capa",
  subtitle_area: "Legendas",
}

function ToolIcon({ type }: { type: El["type"] }) {
  switch (type) {
    case "text":
      return <Type className="size-4" />
    case "shape":
      return <Square className="size-4" />
    case "video_slot":
      return <Video className="size-4" />
    case "image":
    case "logo":
      return <ImageIcon className="size-4" />
    case "cover":
      return <LayoutTemplate className="size-4" />
    case "subtitle_area":
      return <Rows3 className="size-4" />
  }
}

function hexWithAlpha(hex: string, alpha: number): string {
  const m = hex.replace("#", "")
  const bigint = parseInt(m.length === 3 ? m.split("").map((c) => c + c).join("") : m, 16)
  if (Number.isNaN(bigint)) return `rgba(0,0,0,${alpha})`
  const r = (bigint >> 16) & 255
  const g = (bigint >> 8) & 255
  const b = bigint & 255
  return `rgba(${r},${g},${b},${alpha})`
}

function handlePos(pos: EPos): React.CSSProperties {
  const style: React.CSSProperties = { position: "absolute", zIndex: 20 }
  const half = -5
  if (pos.includes("n")) {
    style.top = half
  }
  if (pos.includes("s")) {
    style.bottom = half
  }
  if (pos.includes("e")) {
    style.right = half
  }
  if (pos.includes("w")) {
    style.left = half
  }
  if (pos === "n" || pos === "s") style.left = "50%"
  if (pos === "e" || pos === "w") style.top = "50%"
  if (pos === "n" || pos === "s" || pos === "e" || pos === "w") {
    style.transform = "translate(-50%, -50%)"
  }
  return style
}

function CanvasBackground({ background }: { background: Record<string, unknown> }) {
  const type = background.type as string
  if (type === "color") {
    return <div className="absolute inset-0" style={{ background: (background.value as string) ?? "#000000" }} />
  }
  if (type === "gradient") {
    const val = (background.value as Record<string, unknown>) ?? {}
    const colors = ((val.colors as string[]) ?? ["#7C3AED", "#DB2777"])
    const angle = Number(val.angle ?? 0)
    return (
      <div
        className="absolute inset-0"
        style={{ background: `linear-gradient(${angle}deg, ${colors.join(", ")})` }}
      />
    )
  }
  if (type === "image" && background.value) {
    return <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: `url(${mediaUrl(background.value as string)})` }} />
  }
  return <div className="absolute inset-0 bg-black" />
}

function TextPreview({ el }: { el: El }) {
  const s = el.style
  const size = Math.min(Number(s.font_size ?? 72) * SCALE, el.h * CANVAS_H * 0.9)
  return (
    <div
      className="flex h-full w-full items-center justify-center whitespace-pre-wrap break-words px-1 text-center"
      style={{
        color: (s.color as string) ?? "#FFFFFF",
        fontSize: size,
        fontWeight: Number(s.weight ?? 400),
        textAlign: (s.align as string) as React.CSSProperties["textAlign"],
        WebkitTextStroke: s.outline_width ? `${Number(s.outline_width) * SCALE}px ${s.outline_color ?? "#000000"}` : undefined,
        fontFamily: s.font ? String(s.font) : undefined,
        lineHeight: 1.1,
      }}
    >
      {String(el.content ?? "")}
    </div>
  )
}

export function TemplateEditor({
  open,
  onOpenChange,
  templateId,
  onSaved,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  templateId?: string | null
  onSaved: (t: Template) => void
}) {
  const [tpl, setTpl] = useState<EditorState>({
    name: "",
    category: "geral",
    description: "",
    background: { type: "none" },
    elements: [],
    subtitle_style_override: null,
  })
  const [loaded, setLoaded] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState(false)
  const [saving, setSaving] = useState(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<DragState | null>(null)

  useEffect(() => {
    if (!open) return
    setLoaded(false)
    setSelectedId(null)
    setPreviewUrl(null)
    if (templateId) {
      getTemplate(templateId)
        .then((t) => {
          setTpl({
            name: t.name,
            category: t.category,
            description: t.description || "",
            background: { ...t.background },
            elements: t.elements.map((e) => ({ ...e, style: { ...e.style } })),
            subtitle_style_override: t.subtitle_style_override,
          })
          setLoaded(true)
        })
        .catch((e) => {
          toast.error(e instanceof Error ? e.message : "Falha ao carregar")
          setLoaded(true)
        })
    } else {
      setTpl({ name: "", category: "geral", description: "", background: { type: "none" }, elements: [], subtitle_style_override: null })
      setLoaded(true)
    }
  }, [open, templateId])

  const updateEl = useCallback((id: string, patch: Partial<El>) => {
    setTpl((t) => ({ ...t, elements: t.elements.map((e) => (e.id === id ? { ...e, ...patch } : e)) }))
  }, [])

  const updateStyle = useCallback((id: string, style: Record<string, unknown>) => {
    setTpl((t) => ({ ...t, elements: t.elements.map((e) => (e.id === id ? { ...e, style: { ...e.style, ...style } } : e)) }))
  }, [])

  const addElement = (type: El["type"]) => {
    const el = makeElement(type)
    setTpl((t) => ({ ...t, elements: [...t.elements, el] }))
    setSelectedId(el.id)
  }

  const removeElement = (id: string) => {
    setTpl((t) => ({ ...t, elements: t.elements.filter((e) => e.id !== id) }))
    setSelectedId((s) => (s === id ? null : s))
  }

  const duplicateElement = (id: string) => {
    const src = tpl.elements.find((e) => e.id === id)
    if (!src) return
    const copy: El = {
      ...src,
      id: newId("e"),
      style: { ...src.style },
      x: clamp(src.x + 0.02, 0, 1 - src.w),
      y: clamp(src.y + 0.02, 0, 1 - src.h),
    }
    setTpl((t) => ({ ...t, elements: [...t.elements, copy] }))
    setSelectedId(copy.id)
  }

  const doPreview = async () => {
    setPreviewUrl(null)
    setPreviewing(true)
    try {
      const res = await previewTemplate({
        id: templateId ?? undefined,
        name: tpl.name,
        category: tpl.category,
        description: tpl.description,
        background: tpl.background,
        elements: tpl.elements,
        subtitle_style_override: tpl.subtitle_style_override,
      })
      setPreviewUrl(mediaUrl(res.thumbnail))
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha no preview")
    } finally {
      setPreviewing(false)
    }
  }

  const doSave = async (isPublic: boolean) => {
    if (!tpl.name?.trim()) {
      toast.error("Dê um nome ao template")
      return
    }
    setSaving(true)
    const payload = {
      name: tpl.name.trim(),
      category: tpl.category,
      description: tpl.description,
      background: tpl.background,
      elements: tpl.elements,
      subtitle_style_override: tpl.subtitle_style_override,
      is_public: isPublic,
    }
    try {
      const saved = templateId ? await updateTemplate(templateId, payload) : await createTemplate(payload)
      onSaved(saved)
      toast.success(isPublic ? "Template publicado" : "Rascunho salvo")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar")
    } finally {
      setSaving(false)
    }
  }

  // ---- drag / resize (vanilla, mousemove/mouseup no window) ----
  const onDragMove = useCallback(
    (e: MouseEvent) => {
      const d = dragRef.current
      if (!d) return
      const fx = (e.clientX - d.startX) / d.Wpx
      const fy = (e.clientY - d.startY) / d.Hpx
      const o = d.orig
      let { x, y, w, h } = o
      if (d.mode === "move") {
        x = clamp(o.x + fx, 0, 1 - o.w)
        y = clamp(o.y + fy, 0, 1 - o.h)
      } else {
        if (d.handle.includes("e")) w = clamp(o.w + fx, MIN_SIZE, 1 - o.x)
        if (d.handle.includes("s")) h = clamp(o.h + fy, MIN_SIZE, 1 - o.y)
        if (d.handle.includes("w")) {
          const nx = clamp(o.x + fx, 0, o.x + o.w - MIN_SIZE)
          w = o.w + (o.x - nx)
          x = nx
        }
        if (d.handle.includes("n")) {
          const ny = clamp(o.y + fy, 0, o.y + o.h - MIN_SIZE)
          h = o.h + (o.y - ny)
          y = ny
        }
      }
      d.orig = { x, y, w, h }
      updateEl(d.id, { x, y, w, h })
    },
    [updateEl],
  )

  const onDragEnd = useCallback(() => {
    dragRef.current = null
    window.removeEventListener("mousemove", onDragMove)
    window.removeEventListener("mouseup", onDragEnd)
  }, [onDragMove])

  useEffect(
    () => () => {
      window.removeEventListener("mousemove", onDragMove)
      window.removeEventListener("mouseup", onDragEnd)
    },
    [onDragMove, onDragEnd],
  )

  const startDrag = (e: React.MouseEvent, id: string, mode: "move" | "resize", handle?: EPos) => {
    e.preventDefault()
    e.stopPropagation()
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const el = tpl.elements.find((x) => x.id === id)
    if (!el) return
    dragRef.current = {
      mode,
      handle: handle ?? "se",
      id,
      startX: e.clientX,
      startY: e.clientY,
      orig: { x: el.x, y: el.y, w: el.w, h: el.h },
      Wpx: rect.width,
      Hpx: rect.height,
    }
    setSelectedId(id)
    window.addEventListener("mousemove", onDragMove)
    window.addEventListener("mouseup", onDragEnd)
  }

  const elementStyle = (el: El, isSel: boolean): React.CSSProperties => {
    const s = el.style
    const left = el.x * CANVAS_W
    const top = el.y * CANVAS_H
    const width = el.w * CANVAS_W
    const height = el.h * CANVAS_H
    const base: React.CSSProperties = { position: "absolute", left, top, width, height }
    const outline = isSel ? "2px solid #818cf8" : "1px dashed rgba(255,255,255,0.28)"
    switch (el.type) {
      case "shape":
        return {
          ...base,
          borderRadius: s.shape === "circle" ? "50%" : 8,
          background: hexWithAlpha(String(s.color ?? "#000000"), Number(s.opacity ?? 1)),
          boxShadow: s.outline ? `0 0 0 ${Number(s.outline)}px ${String(s.outline_color ?? "#FFFFFF")}` : undefined,
          outline,
        }
      case "cover":
        return { ...base, borderRadius: 8, background: `rgba(0,0,0,${Number(s.opacity ?? 0.4)})`, outline }
      case "image":
      case "logo":
      case "video_slot":
        return { ...base, outline, overflow: "hidden" }
      default:
        return { ...base, outline }
    }
  }

  const renderHandle = (el: El, pos: EPos) => (
    <div
      key={pos}
      onMouseDown={(e) => startDrag(e, el.id, "resize", pos)}
      className="absolute size-2.5 rounded-sm border border-white bg-indigo-400"
      style={handlePos(pos)}
    />
  )

  const selection = tpl.elements.find((e) => e.id === selectedId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[92vh] w-[98vw] max-w-[1200px] flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-4 py-3">
          <div className="flex items-center gap-3">
            <DialogTitle className="flex items-center gap-2 text-base">
              <LayoutTemplate className="size-4" />
              Editor de Template
            </DialogTitle>
            <DialogDescription className="sr-only">
              Editor visual WYSIWYG de templates de corte 9:16. Arraste para mover, use as alças para redimensionar.
            </DialogDescription>
            <div className="ml-auto flex items-center gap-2">
              <Button size="sm" variant="outline" onClick={() => void doSave(false)} disabled={saving || !loaded}>
                {saving ? <Loader2 className="animate-spin" /> : null} Salvar rascunho
              </Button>
              <Button size="sm" onClick={() => void doSave(true)} disabled={saving || !loaded}>
                Publicar
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className="grid min-h-0 flex-1 grid-cols-[48px_minmax(0,1fr)_300px] overflow-hidden">
          <div className="flex flex-col items-center gap-1 overflow-y-auto border-r border-border bg-muted/20 p-2">
            {(["text", "shape", "video_slot", "image", "logo", "cover", "subtitle_area"] as const).map((type) => (
              <button
                key={type}
                type="button"
                title={ELEMENT_LABEL[type]}
                onClick={() => addElement(type)}
                className="flex size-9 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <ToolIcon type={type} />
              </button>
            ))}
          </div>

          <div className="flex min-w-0 items-center justify-center overflow-auto bg-background p-4">
            <div
              ref={canvasRef}
              className="relative shrink-0 rounded-md bg-black shadow-xl"
              style={{ width: CANVAS_W, height: CANVAS_H }}
              onMouseDown={(e) => {
                if (e.target === canvasRef.current) setSelectedId(null)
              }}
            >
              <CanvasBackground background={tpl.background} />
              {tpl.elements.map((el) => {
                const isSel = selectedId === el.id
                return (
                  <div
                    key={el.id}
                    className="cursor-move"
                    style={elementStyle(el, isSel)}
                    onMouseDown={(e) => startDrag(e, el.id, "move")}
                  >
                    {el.type === "text" && el.content ? <TextPreview el={el} /> : null}
                    {el.type === "text" && !el.content ? (
                      <div className="flex h-full w-full items-center justify-center text-[10px] uppercase text-muted-foreground">texto</div>
                    ) : null}
                    {el.type === "video_slot" ? (
                      <div className="flex h-full w-full items-center justify-center bg-black/70 text-[10px] uppercase tracking-wider text-white/60">
                        <Video className="mr-1 size-3" /> vídeo
                      </div>
                    ) : null}
                    {el.type === "image" || el.type === "logo" ? (
                      el.content ? (
                        <img src={mediaUrl(el.content)} alt="" className="h-full w-full object-contain" />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                          <ImageIcon className="size-5" />
                        </div>
                      )
                    ) : null}
                    {el.type === "subtitle_area" ? (
                      <div className="flex h-full w-full items-center justify-center text-[10px] uppercase tracking-wider text-emerald-300/70">
                        <Rows3 className="mr-1 size-4" /> legendas
                      </div>
                    ) : null}
                    {el.type === "cover" ? (
                      <div className="flex h-full w-full items-center justify-center text-[10px] uppercase tracking-wider text-white/50">capa</div>
                    ) : null}
                    {isSel &&
                      (["n", "s", "e", "w", "ne", "nw", "se", "sw"] as const).map((pos) => renderHandle(el, pos))}
                  </div>
                )
              })}
            </div>
          </div>

          <ScrollArea className="h-full min-h-0 border-l border-border">
            <div className="flex flex-col gap-4 p-3">
              <div className="grid grid-cols-2 gap-2">
                <div className="col-span-2">
                  <Label className="text-[10px] text-muted-foreground">Nome</Label>
                  <Input value={tpl.name} onChange={(e) => setTpl((t) => ({ ...t, name: e.target.value }))} placeholder="Nome do template" className="h-8" />
                </div>
                <div className="col-span-2">
                  <Label className="text-[10px] text-muted-foreground">Categoria</Label>
                  <Select value={tpl.category} onValueChange={(v) => setTpl((t) => ({ ...t, category: v ?? t.category }))}>
                    <SelectTrigger className="h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between">
                <span className="text-xs font-medium">Preview</span>
                <Button size="sm" variant="outline" onClick={() => void doPreview()} disabled={previewing}>
                  {previewing ? <Loader2 className="animate-spin" /> : <Play />} Renderizar
                </Button>
              </div>
              {previewUrl && (
                <img src={previewUrl} alt="Preview do template" className="aspect-[9/16] w-full rounded-md border border-border object-cover" />
              )}

              <Separator />

              {selection ? (
                <SelectionPanel
                  el={selection}
                  onContent={(v) => updateEl(selection.id, { content: v })}
                  onStyle={(p) => updateStyle(selection.id, p)}
                  onPos={(key, v) => {
                    const value = clamp(v / 100, 0, 1)
                    const patch: Partial<El> = { [key]: value }
                    if (key === "w") patch.x = clamp(selection.x, 0, 1 - value)
                    if (key === "h") patch.y = clamp(selection.y, 0, 1 - value)
                    updateEl(selection.id, patch)
                  }}
                  onRemove={() => removeElement(selection.id)}
                  onDuplicate={() => duplicateElement(selection.id)}
                />
              ) : (
                <BackgroundPanel
                  background={tpl.background}
                  onChange={(bg) => setTpl((t) => ({ ...t, background: bg }))}
                />
              )}
            </div>
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function SelectionPanel({
  el,
  onContent,
  onStyle,
  onPos,
  onRemove,
  onDuplicate,
}: {
  el: El
  onContent: (v: string) => void
  onStyle: (s: Record<string, unknown>) => void
  onPos: (k: "x" | "y" | "w" | "h", v: number) => void
  onRemove: () => void
  onDuplicate: () => void
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">{ELEMENT_LABEL[el.type]}</span>
        <div className="flex items-center gap-1">
          <button type="button" onClick={onDuplicate} title="Duplicar" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            <Copy className="size-3.5" />
          </button>
          <button type="button" onClick={onRemove} title="Remover" className="rounded p-1 text-red-400 hover:bg-muted">
            <Trash2 className="size-3.5" />
          </button>
        </div>
      </div>

      {(el.type === "text" || el.type === "image" || el.type === "logo") && (
        <div>
          <Label className="text-[10px] text-muted-foreground">
            {el.type === "text" ? "Conteúdo" : "Caminho da imagem (ex.: data/...)"}
          </Label>
          <Textarea
            value={el.content ?? ""}
            onChange={(e) => onContent(e.target.value)}
            rows={el.type === "text" ? 2 : 1}
            className="h-auto min-h-9 text-xs"
            placeholder={el.type === "text" ? "Texto a exibir" : "path/to/image.png"}
          />
        </div>
      )}

      <PosGrid el={el} onPos={(k, v) => onPos(k, v)} />

      {el.type === "text" && (
        <>
          <div className="flex items-center gap-1">
            {([["left", AlignLeft], ["center", AlignCenter], ["right", AlignRight]] as const).map(([align, Icon]) => (
              <button
                key={align}
                type="button"
                onClick={() => onStyle({ align })}
                className={cn("flex size-7 items-center justify-center rounded-md", el.style.align === align ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted")}
              >
                <Icon className="size-3.5" />
              </button>
            ))}
            <button
              type="button"
              onClick={() => onStyle({ weight: Number(el.style.weight ?? 400) >= 700 ? 400 : 700 })}
              className={cn("flex size-7 items-center justify-center rounded-md", Number(el.style.weight ?? 400) >= 700 ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted")}
              title="Negrito"
            >
              <Bold className="size-3.5" />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-[10px] text-muted-foreground">Tamanho (px)</Label>
              <Input type="number" value={Number(el.style.font_size ?? 72)} onChange={(e) => onStyle({ font_size: Number(e.target.value) })} className="h-8" />
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">Cor</Label>
              <Input type="color" value={String(el.style.color ?? "#FFFFFF")} onChange={(e) => onStyle({ color: e.target.value })} className="h-8 cursor-pointer p-1" />
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">Borda</Label>
              <Input type="color" value={String(el.style.outline_color ?? "#000000")} onChange={(e) => onStyle({ outline_color: e.target.value })} className="h-8 cursor-pointer p-1" />
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">Largura borda</Label>
              <Input type="number" value={Number(el.style.outline_width ?? 0)} onChange={(e) => onStyle({ outline_width: Number(e.target.value) })} className="h-8" />
            </div>
          </div>
        </>
      )}

      {el.type === "shape" && (
        <>
          <div>
            <Label className="text-[10px] text-muted-foreground">Forma</Label>
            <Select value={String(el.style.shape ?? "rect")} onValueChange={(v) => onStyle({ shape: v })}>
              <SelectTrigger className="h-8">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="rect">Retângulo</SelectItem>
                <SelectItem value="circle">Círculo</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-[10px] text-muted-foreground">Cor</Label>
              <Input type="color" value={String(el.style.color ?? "#DC2626")} onChange={(e) => onStyle({ color: e.target.value })} className="h-8 cursor-pointer p-1" />
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">Opacidade</Label>
              <Input type="number" min={0} max={1} step={0.05} value={Number(el.style.opacity ?? 1)} onChange={(e) => onStyle({ opacity: Number(e.target.value) })} className="h-8" />
            </div>
            <div>
              <Label className="text-[10px] text-muted-foreground">Contorno (px)</Label>
              <Input type="number" min={0} value={Number(el.style.outline ?? 0)} onChange={(e) => onStyle({ outline: Number(e.target.value) })} className="h-8" />
            </div>
            {Number(el.style.outline ?? 0) > 0 && (
              <div>
                <Label className="text-[10px] text-muted-foreground">Cor contorno</Label>
                <Input type="color" value={String(el.style.outline_color ?? "#FFFFFF")} onChange={(e) => onStyle({ outline_color: e.target.value })} className="h-8 cursor-pointer p-1" />
              </div>
            )}
          </div>
        </>
      )}

      {el.type === "cover" && (
        <div>
          <Label className="text-[10px] text-muted-foreground">Opacidade</Label>
          <Input type="number" min={0} max={1} step={0.05} value={Number(el.style.opacity ?? 0.4)} onChange={(e) => onStyle({ opacity: Number(e.target.value) })} className="h-8" />
        </div>
      )}
    </div>
  )
}

// posição via canal direto: reutiliza o updater de estilo/posição do pai
function PosGrid({ el, onPos }: { el: El; onPos: (k: "x" | "y" | "w" | "h", v: number) => void }) {
  const field = (k: "x" | "y" | "w" | "h", label: string) => (
    <div key={k}>
      <Label className="text-[10px] text-muted-foreground">{label} (%)</Label>
      <Input type="number" value={Math.round(el[k] * 100)} onChange={(e) => onPos(k, Number(e.target.value))} className="h-8" />
    </div>
  )
  return (
    <div className="grid grid-cols-4 gap-2">
      {field("x", "X")}
      {field("y", "Y")}
      {field("w", "Larg")}
      {field("h", "Alt")}
    </div>
  )
}

function BackgroundPanel({ background, onChange }: { background: Record<string, unknown>; onChange: (bg: Record<string, unknown>) => void }) {
  const type = String(background.type ?? "none")
  const set = (patch: Record<string, unknown>) => onChange({ ...background, ...patch })
  return (
    <div className="flex flex-col gap-3">
      <span className="text-xs font-medium">Fundo</span>
      <div>
        <Label className="text-[10px] text-muted-foreground">Tipo</Label>
        <Select value={type} onValueChange={(v) => set({ type: v })}>
          <SelectTrigger className="h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">Nenhum (vídeo ocupa tudo)</SelectItem>
            <SelectItem value="color">Cor sólida</SelectItem>
            <SelectItem value="gradient">Gradiente</SelectItem>
            <SelectItem value="image">Imagem</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {type === "color" && (
        <div>
          <Label className="text-[10px] text-muted-foreground">Cor</Label>
          <Input type="color" value={String(background.value ?? "#111827")} onChange={(e) => set({ value: e.target.value })} className="h-8 w-24 cursor-pointer p-1" />
        </div>
      )}
      {type === "gradient" && (
        <GradientFields value={background.value} onChange={(v) => set({ value: v })} />
      )}
      {type === "image" && (
        <div>
          <Label className="text-[10px] text-muted-foreground">Caminho da imagem (data/...)</Label>
          <Input value={String(background.value ?? "")} onChange={(e) => set({ value: e.target.value })} className="h-8 text-xs" placeholder="data/logo.png" />
        </div>
      )}
    </div>
  )
}

function GradientFields({ value, onChange }: { value: unknown; onChange: (v: Record<string, unknown>) => void }) {
  const val = (value as Record<string, unknown>) ?? {}
  const colors = ((val.colors as string[]) ?? ["#7C3AED", "#DB2777"])
  const setColor = (i: number, c: string) => {
    const next = [...colors]
    next[i] = c
    onChange({ colors: next, angle: Number(val.angle ?? 0) })
  }
  return (
    <div className="flex flex-col gap-2">
      {colors.map((c, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-14 text-[10px] text-muted-foreground">Cor {i + 1}</span>
          <Input type="color" value={c} onChange={(e) => setColor(i, e.target.value)} className="h-8 w-24 cursor-pointer p-1" />
        </div>
      ))}
      <div>
        <Label className="text-[10px] text-muted-foreground">Ângulo</Label>
        <Input type="number" value={Number(val.angle ?? 0)} onChange={(e) => onChange({ colors, angle: Number(e.target.value) })} className="h-8" />
      </div>
    </div>
  )
}