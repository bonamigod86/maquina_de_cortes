import { useEffect, useMemo, useState } from "react"
import { Check, Copy, LayoutTemplate, Pencil, Plus, Search } from "lucide-react"
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
import { TemplateEditor } from "@/components/TemplateEditor"
import { cloneTemplate, listTemplates, mediaUrl } from "@/lib/api"
import type { Template } from "@/lib/types"
import { cn } from "@/lib/utils"

const CATEGORY_LABEL: Record<string, string> = {
  podcast: "Podcast",
  viral: "Viral",
  news: "Notícia",
  gaming: "Gaming",
  minimal: "Mínimo",
  geral: "Geral",
}

export function TemplateGallery({
  open,
  onOpenChange,
  onSelect,
  currentId,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onSelect: (t: Template) => void
  currentId?: string | null
}) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [filter, setFilter] = useState<"all" | "public" | "mine">("all")
  const [query, setQuery] = useState("")
  const [editorId, setEditorId] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    if (!open) return
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]))
  }, [open])

  const editorOpen = editorId !== undefined

  const refresh = () => {
    setEditorId(undefined)
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]))
  }

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return templates.filter((t) => {
      if (filter === "public" && t.is_builtin) return true
      if (filter === "mine" && !t.is_builtin) return true
      if (filter === "all") return true
      if (!q) return true
      return t.name.toLowerCase().includes(q) || t.category.toLowerCase().includes(q)
    })
  }, [templates, filter, query])

  const doClone = async (id: string) => {
    try {
      await cloneTemplate(id)
      setTemplates(await listTemplates())
      toast.success("Duplicado para Meus templates")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao duplicar")
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Template de corte</DialogTitle>
          <DialogDescription>Escolha um layout visual para aplicar ao corte.</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar template…" className="h-9 pl-8" />
          </div>
          <Button size="sm" variant="outline" onClick={() => setEditorId(null)}>
            <Plus /> Novo
          </Button>
          <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
            {([
              ["all", "Todos"],
              ["public", "Galeria"],
              ["mine", "Meus"],
            ] as const).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setFilter(k)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                  filter === k ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-3 overflow-y-auto p-1 sm:grid-cols-3">
          {filtered.length === 0 && (
            <div className="col-span-full mt-10 text-center text-xs text-muted-foreground">
              Nenhum template encontrado.
            </div>
          )}
          {filtered.map((t) => {
            const active = currentId === t.id
            return (
              <div key={t.id} className="group flex flex-col overflow-hidden rounded-lg border border-border bg-card">
                <div className="relative aspect-[9/16] w-full bg-muted/40">
                  {t.thumbnail ? (
                    <img src={mediaUrl(t.thumbnail)} alt={t.name} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                      <LayoutTemplate className="size-8" />
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => onSelect(t)}
                    className={cn(
                      "absolute right-1.5 top-1.5 flex size-7 items-center justify-center rounded-md shadow",
                      active ? "bg-emerald-500 text-white" : "bg-background/90 text-foreground hover:bg-background",
                    )}
                    title={active ? "Aplicado" : "Usar este template"}
                  >
                    {active ? <Check className="size-4" /> : <LayoutTemplate className="size-4" />}
                  </button>
                </div>
                <div className="flex items-center justify-between gap-1 p-2">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium">{t.name}</p>
                    <p className="text-[10px] text-muted-foreground">{CATEGORY_LABEL[t.category] ?? t.category}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      title="Editar"
                      onClick={() => setEditorId(t.id)}
                      className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      <Pencil className="size-3.5" />
                    </button>
                    {!t.is_builtin && (
                      <button
                        type="button"
                        title="Duplicar"
                        onClick={() => void doClone(t.id)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <Copy className="size-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="flex justify-end">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Fechar</Button>
        </div>
      </DialogContent>

      <TemplateEditor
        open={editorOpen}
        onOpenChange={(v) => {
          if (!v) setEditorId(undefined)
        }}
        templateId={editorId}
        onSaved={refresh}
      />
    </Dialog>
  )
}