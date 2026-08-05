import { useCallback, useEffect, useRef, useState } from "react"
import {
  Clapperboard,
  Download,
  Link2,
  Loader2,
  MonitorPlay,
  Play,
  Settings,
  Smartphone,
  Square,
  Trash2,
  Upload,
  X,
} from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { BrandKitPanel } from "@/components/BrandKitPanel"
import { cn, fmtBytes, fmtTime } from "@/lib/utils"
import { cancelProject, deleteProject, getAvailableModels, getProject, getSettings, importFromUrl, processProject, updateSettings, uploadVideo, convertShorts } from "@/lib/api"
import type { Project, Settings as SettingsType } from "@/lib/types"

const STATUS_STYLE: Record<string, string> = {
  ready: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  processing: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  queued: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  downloading: "bg-sky-500/15 text-sky-400 border-sky-500/30",
  error: "bg-red-500/15 text-red-400 border-red-500/30",
  created: "bg-muted text-muted-foreground border-border",
}

const STATUS_LABEL: Record<string, string> = {
  ready: "Pronto",
  processing: "Processando",
  queued: "Na fila",
  downloading: "Baixando",
  error: "Erro",
  created: "Novo",
}

function YoutubeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M23.5 6.19a3.02 3.02 0 0 0-2.12-2.14C19.5 3.55 12 3.55 12 3.55s-7.5 0-9.38.5A3.02 3.02 0 0 0 .5 6.19C0 8.07 0 12 0 12s0 3.93.5 5.81a3.02 3.02 0 0 0 2.12 2.14c1.88.5 9.38.5 9.38.5s7.5 0 9.38-.5a3.02 3.02 0 0 0 2.12-2.14C24 15.93 24 12 24 12s0-3.93-.5-5.81zM9.55 15.57V8.43L15.82 12l-6.27 3.57z" />
    </svg>
  )
}

function TwitchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z" />
    </svg>
  )
}

function KickIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden>
      <path d="M2 2h5.8l3.4 3.4L12.6 2h3.8v4.4l-3.2 3.2 3.2 3.2v4.4h-3.8l-1.4-1.4V22H7.8v-6.8H2zm10 9.4v-1.4h-3v1.4zm-3-4v-1.4h3v1.4z" />
    </svg>
  )
}

function ImportDialog({ open, onOpenChange, onImported }: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onImported: (id: string) => void
}) {
  const [progress, setProgress] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [mode, setMode] = useState<"file" | "link">("file")
  const [url, setUrl] = useState("")
  const [platform, setPlatform] = useState("youtube")
  const [quality, setQuality] = useState("1080p")
  const [dlBusy, setDlBusy] = useState(false)
  const [dlMsg, setDlMsg] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  const doUpload = useCallback(async (file: File) => {
    setUploading(true)
    setProgress(0)
    try {
      const res = await uploadVideo(file, setProgress)
      toast.success(`Vídeo importado: ${res.project.name}`)
      onOpenChange(false)
      onImported(res.upload_id)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha no upload")
    } finally {
      setUploading(false)
    }
  }, [onImported, onOpenChange])

  const doImportUrl = async () => {
    if (!url.trim()) {
      toast.error("Cole o link do vídeo")
      return
    }
    setDlBusy(true)
    setDlMsg(platform === "twitch" || platform === "kick" ? `Conectando ao ${platform}…` : "Conectando à plataforma…")
    try {
      const res = await importFromUrl(url.trim(), quality, platform)
      setDlMsg("Baixando o vídeo…")
      for (;;) {
        await new Promise((r) => setTimeout(r, 2000))
        const p = await getProject(res.upload_id)
        if (p.status === "downloading") continue
        if (p.status === "error") {
          toast.error(p.error || "Falha ao baixar o vídeo")
          break
        }
        toast.success(`Vídeo importado: ${p.name}`)
        onOpenChange(false)
        onImported(p.id)
        break
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao importar")
    } finally {
      setDlBusy(false)
      setDlMsg("")
    }
  }

  const busy = uploading || dlBusy

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!busy) onOpenChange(v) }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Importar vídeo</DialogTitle>
          <DialogDescription>
            Arquivo local ou link (YouTube, Twitch, Kick…), processado 100% localmente.
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
          {([
            ["file", "Arquivo"],
            ["link", "Link"],
          ] as const).map(([k, label]) => (
            <button
              key={k}
              type="button"
              onClick={() => setMode(k)}
              className={cn(
                "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                mode === k ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {mode === "file" ? (
          <>
            <div
              className={cn(
                "flex flex-col items-center gap-3 rounded-xl border-2 border-dashed p-10 text-center transition-colors",
                dragOver ? "border-primary bg-primary/5" : "border-border",
              )}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setDragOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f) void doUpload(f)
              }}
              onClick={() => inputRef.current?.click()}
            >
              <Upload className="size-8 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium">Arraste o vídeo aqui</p>
                <p className="text-xs text-muted-foreground">ou clique para selecionar</p>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) void doUpload(f)
                  e.target.value = ""
                }}
              />
            </div>
            {uploading && (
              <div className="flex items-center gap-3">
                <Progress value={progress * 100} className="h-2" />
                <span className="shrink-0 text-xs text-muted-foreground">{Math.round(progress * 100)}%</span>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Plataforma</label>
              <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
{([
                  ["youtube", "YouTube", YoutubeIcon],
                  ["twitch", "Twitch", TwitchIcon],
                  ["kick", "Kick", KickIcon],
                  ["outros", "Outros", Link2],
                ] as const).map(([k, label, Icon]) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setPlatform(k)}
                    className={cn(
                      "flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors",
                      platform === k
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="size-3.5 shrink-0" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Link do vídeo</label>
              <div className="flex items-center gap-2">
                <Input
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={
                    platform === "twitch"
                      ? "https://www.twitch.tv/videos/…"
                      : platform === "kick"
                        ? "https://kick.com/…/videos/…"
                        : "https://www.youtube.com/watch?v=…"
                  }
                  className="h-9 flex-1"
                  disabled={dlBusy}
                  onKeyDown={(e) => { if (e.key === "Enter" && !dlBusy) void doImportUrl() }}
                />
                <Button onClick={() => void doImportUrl()} disabled={dlBusy}>
                  {dlBusy ? <Loader2 className="animate-spin" /> : <MonitorPlay />}
                  Importar
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <label className="shrink-0 text-xs text-muted-foreground">Qualidade</label>
              <select
                className="h-8 flex-1 rounded-md border border-input bg-background px-2 text-xs disabled:opacity-50"
                value={quality}
                onChange={(e) => setQuality(e.target.value)}
                disabled={dlBusy}
              >
                <option value="360p">360p</option>
                <option value="720p">720p</option>
                <option value="1080p">1080p (recomendado)</option>
                <option value="source">Original (máxima)</option>
              </select>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Link2 className="size-3.5 shrink-0" />
              {(platform === "twitch" || platform === "kick")
                ? "Baixa VODs na qualidade escolhida. Suporta live e clipes."
                : "Baixa o melhor vídeo até a qualidade escolhida (yt-dlp)."}
            </div>
            {dlBusy && (
              <div className="flex items-center gap-2 text-xs text-sky-400">
                <Loader2 className="size-3.5 animate-spin" /> {dlMsg}
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export function LeftPanel({ projects, selectedId, onSelect, onRefresh }: {
  projects: Project[]
  selectedId: string | null
  onSelect: (id: string) => void
  onRefresh: () => void
}) {
  const [importOpen, setImportOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)

  const handleProcess = async (id: string) => {
    setBusyId(id)
    try {
      await processProject(id)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao iniciar processamento")
    } finally {
      setBusyId(null)
      onRefresh()
    }
  }

  const handleCancel = async (id: string) => {
    setBusyId(id)
    try {
      await cancelProject(id)
    } catch {
      /* ignore */
    } finally {
      setBusyId(null)
      onRefresh()
    }
  }

  const handleConvert = async (id: string) => {
    setBusyId(id)
    try {
      await convertShorts(id)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao iniciar conversão")
    } finally {
      setBusyId(null)
      onRefresh()
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm("Apagar este projeto e todos os arquivos gerados?")) return
    try {
      await deleteProject(id)
      if (selectedId === id) onSelect("")
      onRefresh()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao apagar")
    }
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-background">
      <div className="flex items-center justify-between border-b border-border p-3">
        <span className="text-sm font-semibold">Projetos</span>
        <Button size="icon-sm" variant="ghost" onClick={() => setImportOpen(true)} title="Importar vídeo">
          <Upload />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {projects.length === 0 && (
          <div className="mt-10 px-4 text-center text-xs text-muted-foreground">
            Nenhum projeto ainda.
            <br />
            Importe um vídeo para começar.
          </div>
        )}
        <div className="space-y-1.5">
          {projects.map((p) => (
            <div
              key={p.id}
              className={cn(
                "group cursor-pointer rounded-lg border p-2.5 transition-colors",
                selectedId === p.id
                  ? "border-primary/50 bg-primary/10"
                  : "border-border bg-card hover:bg-muted/50",
              )}
              onClick={() => onSelect(p.id)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">{p.name}</span>
                <span className={cn("shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium", STATUS_STYLE[p.status])}>
                  {STATUS_LABEL[p.status] ?? p.status}
                </span>
              </div>
              <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{p.duration ? fmtTime(p.duration) : "—"}</span>
                <span>{p.clip_count > 0 ? `${p.clip_count} cortes` : fmtBytes(p.source_size)}</span>
              </div>
              {p.status === "processing" && (
                <Progress value={p.progress * 100} className="mt-2 h-1" />
              )}
              {p.error && p.status === "error" && (
                <p className="mt-1 line-clamp-2 text-[11px] text-red-400">{p.error}</p>
              )}
              <div className="mt-1.5 hidden flex-wrap gap-1 group-hover:flex" onClick={(e) => e.stopPropagation()}>
                {p.status !== "processing" && (
                  <Button
                    size="xs"
                    variant="outline"
                    disabled={busyId === p.id}
                    onClick={() => void handleProcess(p.id)}
                  >
                    {busyId === p.id ? <Loader2 className="animate-spin" /> : <Play />}
                    Processar
                  </Button>
                )}
                {p.status === "processing" && (
                  <Button size="xs" variant="outline" onClick={() => void handleCancel(p.id)}>
                    <Square /> Parar
                  </Button>
                )}
                {p.status === "ready" && (
                  <Button
                    size="xs"
                    variant="ghost"
                    disabled={busyId === p.id}
                    title="Converter o vídeo inteiro para 9:16 (Shorts/Reels), sem legendas nem IA"
                    onClick={() => void handleConvert(p.id)}
                  >
                    {busyId === p.id ? <Loader2 className="animate-spin" /> : <Smartphone />}
                    9:16
                  </Button>
                )}
                {p.status === "ready" && p.has_clips && (
                  <Button
                    size="xs"
                    variant="ghost"
                    title="Exportar todos os cortes"
                    onClick={() => window.dispatchEvent(new CustomEvent("export-all", { detail: p.id }))}
                  >
                    <Clapperboard /> Exportar
                  </Button>
                )}
                <Button size="xs" variant="ghost" className="text-destructive" onClick={() => void handleDelete(p.id)}>
                  <Trash2 />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-border p-2">
        <Button variant="outline" className="w-full justify-start" onClick={() => setSettingsOpen(true)}>
          <Settings /> Configurações
        </Button>
      </div>

      <ImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onImported={(id) => { onSelect(id); onRefresh() }}
      />
      <SettingsDialogWrapper open={settingsOpen} onOpenChange={setSettingsOpen} />
    </aside>
  )
}

function SettingsDialogWrapper({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [settings, setSettings] = useState<SettingsType | null>(null)
  const [models, setModels] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [changed, setChanged] = useState(false)

  useEffect(() => {
    if (!open) return
    getSettings().then(setSettings)
    getAvailableModels().then((m) => setModels(m.models)).catch(() => setModels([]))
    setChanged(false)
  }, [open])

  const save = async () => {
    if (!settings) return
    setSaving(true)
    try {
      const saved = await updateSettings(settings)
      setSettings(saved)
      setChanged(false)
      toast.success("Configurações salvas")
      window.dispatchEvent(new CustomEvent("settings-saved"))
      onOpenChange(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao salvar")
    } finally {
      setSaving(false)
    }
  }

  const set = (patch: Partial<SettingsType>) => {
    setSettings((s) => (s ? { ...s, ...patch } : s))
    setChanged(true)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Configurações</DialogTitle>
          <DialogDescription>Salvas localmente em settings.json</DialogDescription>
        </DialogHeader>
        {settings && (
          <div className="space-y-5 text-sm">
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground">Transcrição (Whisper)</p>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Modelo</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.whisper_model}
                  onChange={(e) => set({ whisper_model: e.target.value })}
                >
                  {["tiny", "base", "small", "medium", "large-v3"].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Idioma</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.language}
                  onChange={(e) => set({ language: e.target.value })}
                >
                  {["auto", "pt", "en", "es", "fr", "de", "it"].map((l) => (
                    <option key={l} value={l}>{l}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground">IA de conteúdo</p>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Provedor</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.ai_provider}
                  onChange={(e) => set({ ai_provider: e.target.value })}
                >
                  <option value="ollama">Ollama (local)</option>
                  <option value="openai_compat">OpenAI-compat (LM Studio etc.)</option>
                  <option value="none">Offline (heurística)</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Modelo</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.ai_model}
                  onChange={(e) => set({ ai_model: e.target.value })}
                >
                  {settings.ai_model && !models.includes(settings.ai_model) && (
                    <option value={settings.ai_model}>{settings.ai_model}</option>
                  )}
                  {models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">URL base</label>
                <Input
                  value={settings.ai_base_url}
                  onChange={(e) => set({ ai_base_url: e.target.value })}
                  className="h-8"
                />
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground">Cortes</p>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Durações (s)</label>
                <Input
                  value={settings.clip_durations.join(",")}
                  onChange={(e) => set({
                    clip_durations: e.target.value.split(",").map((x) => Number(x.trim())).filter((n) => n > 0),
                  })}
                  className="h-8"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Qualidade</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.export_quality}
                  onChange={(e) => set({ export_quality: e.target.value })}
                >
                  <option value="high">Alta (slow, CRF 18)</option>
                  <option value="medium">Média (medium, CRF 23)</option>
                  <option value="fast">Rápida (veryfast, CRF 26)</option>
                </select>
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground">Legendas</p>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Palavras/linha</label>
                <Input
                  type="number"
                  min={1}
                  max={8}
                  value={settings.subtitle_style.words_per_line}
                  onChange={(e) => set({
                    subtitle_style: { ...settings.subtitle_style, words_per_line: Number(e.target.value) || 5 },
                  })}
                  className="h-8 w-20"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Tamanho</label>
                <Input
                  type="number"
                  min={24}
                  max={160}
                  value={settings.subtitle_style.font_size}
                  onChange={(e) => set({
                    subtitle_style: { ...settings.subtitle_style, font_size: Number(e.target.value) || 72 },
                  })}
                  className="h-8 w-20"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Fonte</label>
                <Input
                  value={settings.subtitle_style.font}
                  onChange={(e) => set({ subtitle_style: { ...settings.subtitle_style, font: e.target.value } })}
                  className="h-8"
                />
              </div>
            </div>

            <div className="space-y-5 border-t border-border pt-5">
              <BrandKitPanel settings={settings} set={set} />
            </div>

            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground">Sistema</p>
              <div className="flex items-center gap-2">
                <label className="w-32 shrink-0 text-muted-foreground">Reenquadrar</label>
                <select
                  className="h-8 flex-1 rounded-md border border-input bg-background px-2"
                  value={settings.reframe_mode}
                  onChange={(e) => set({ reframe_mode: e.target.value })}
                >
                  <option value="auto">Automático (sem cortar quando não há rosto)</option>
                  <option value="crop">Sempre cortar (preencher 9:16)</option>
                  <option value="blur">Fundo desfocado (nunca cortar)</option>
                </select>
              </div>
              {[
                { key: "use_gpu" as const, label: "Usar GPU (CUDA)" },
                { key: "face_detection" as const, label: "Detecção de rosto" },
                { key: "download_subtitles" as const, label: "Gerar legendas .srt" },
              ].map((t) => (
                <label key={t.key} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={settings[t.key]}
                    onChange={(e) => set({ [t.key]: e.target.checked })}
                    className="size-4 accent-[var(--primary)]"
                  />
                  {t.label}
                </label>
              ))}
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            <X /> Cancelar
          </Button>
          <Button onClick={() => void save()} disabled={!changed || saving}>
            {saving && <Loader2 className="animate-spin" />}
            <Download /> Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
