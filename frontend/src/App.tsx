import { useCallback, useEffect, useRef, useState } from "react"
import { Cpu, Sparkles, Wifi } from "lucide-react"
import { Toaster } from "sonner"

import { CenterPanel } from "@/components/CenterPanel"
import { LeftPanel } from "@/components/LeftPanel"
import { RightPanel } from "@/components/RightPanel"
import { getProject, getSystemStatus, listProjects, mediaUrl, processProject } from "@/lib/api"
import { useProjectSocket } from "@/lib/useSocket"
import { cn } from "@/lib/utils"
import type { Project, ProjectDetail, SystemStatus } from "@/lib/types"

function Header({ status }: { status: SystemStatus | null }) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-border px-4">
      <div className="flex items-center gap-2">
        <img src="/favicon.svg" alt="Máquina de Cortes" className="size-6" />
        <span className="text-sm font-semibold">Máquina de Cortes</span>
        <span className="text-[11px] text-muted-foreground">— shorts automáticos com legendas</span>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Cpu className={cn("size-3.5", status?.cuda_available ? "text-emerald-400" : "text-muted-foreground")} />
          {status?.cuda_available ? "CUDA" : "CPU"}
        </span>
        <span className="flex items-center gap-1">
          <Sparkles
            className={cn("size-3.5", status?.ai_ok ? "text-emerald-400" : "text-amber-400")}
          />
          <span title={status?.ai_message ?? ""}>
            {status?.ai_ok ? status.ai_provider : "IA offline (heurística)"}
          </span>
        </span>
        {status?.queue?.current && (
          <span className="flex items-center gap-1 text-amber-400">
            <Wifi className="size-3.5" /> processando agora
          </span>
        )}
      </div>
    </header>
  )
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null)
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const refreshProjects = useCallback(() => {
    listProjects().then(setProjects).catch(() => undefined)
  }, [])

  const refreshDetail = useCallback((id: string, silent = false) => {
    getProject(id)
      .then((d) => {
        setDetail((prev) => {
          if (silent && prev) {
            return { ...d, clips: prev.clips }
          }
          return d
        })
      })
      .catch(() => undefined)
  }, [])

  const loadProject = useCallback((id: string) => {
    setSelectedId(id)
    setSelectedClipId(null)
    setCurrentTime(0)
    refreshDetail(id)
  }, [refreshDetail])

  // lista de projetos inicial + refresh a cada 8s
  useEffect(() => {
    refreshProjects()
    const t = setInterval(refreshProjects, 8000)
    return () => clearInterval(t)
  }, [refreshProjects])

  // polling do detail enquanto processa (fallback se WS falhar)
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current)
    if (selectedId) {
      const running = detail?.status === "processing"
      if (running) {
        pollRef.current = setInterval(() => refreshDetail(selectedId), 2500)
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [selectedId, detail?.status, refreshDetail])

  // status do sistema
  const refreshStatus = useCallback(() => {
    getSystemStatus().then(setStatus).catch(() => undefined)
  }, [])

  useEffect(() => {
    refreshStatus()
    const t = setInterval(refreshStatus, 10000)
    return () => clearInterval(t)
  }, [refreshStatus])

  // refresh imediato após salvar configurações (ex.: troca de modelo de IA)
  useEffect(() => {
    window.addEventListener("settings-saved", refreshStatus)
    return () => window.removeEventListener("settings-saved", refreshStatus)
  }, [refreshStatus])

  // eventos WebSocket do projeto selecionado
  useProjectSocket(selectedId, useCallback((e) => {
    if (!selectedId) return
    if (e.type === "step" || e.type === "progress") {
      refreshDetail(selectedId, true)
    } else if (
      e.type === "pipeline_done" ||
      e.type === "pipeline_error" ||
      e.type === "import_done" ||
      e.type === "import_error"
    ) {
      refreshDetail(selectedId)
      refreshProjects()
    }
  }, [selectedId, refreshDetail, refreshProjects]))

  // eventos de atalhos globais dos painéis
  useEffect(() => {
    const onProcess = (ev: Event) => {
      const id = (ev as CustomEvent).detail as string
      if (id) {
        processProject(id).catch(() => undefined)
        refreshDetail(id)
      }
    }
    const onExportAll = (ev: Event) => {
      const id = (ev as CustomEvent).detail as string
      if (id) {
        setSelectedId(id)
        refreshDetail(id)
      }
    }
    window.addEventListener("process-project", onProcess)
    window.addEventListener("export-all", onExportAll)
    return () => {
      window.removeEventListener("process-project", onProcess)
      window.removeEventListener("export-all", onExportAll)
    }
  }, [refreshDetail])

  // remove seleção órfã
  useEffect(() => {
    if (selectedClipId && detail && !detail.clips.some((c) => c.id === selectedClipId)) {
      setSelectedClipId(null)
    }
  }, [detail, selectedClipId])

  const videoUrl = detail?.source ? mediaUrl(detail.source) : ""

  return (
    <div className="flex h-screen flex-col bg-background text-foreground dark">
      <Header status={status} />
      <div className="flex min-h-0 flex-1">
        <LeftPanel
          projects={projects}
          selectedId={selectedId}
          onSelect={loadProject}
          onRefresh={refreshProjects}
        />
        <CenterPanel
          detail={detail ?? emptyDetail(selectedId)}
          currentTime={currentTime}
          selectedClipId={selectedClipId}
          onSeek={setCurrentTime}
          onTimeUpdate={setCurrentTime}
          videoUrl={videoUrl}
        />
        <RightPanel
          detail={detail ?? emptyDetail(selectedId)}
          selectedClipId={selectedClipId}
          currentTime={currentTime}
          onSeek={setCurrentTime}
          onSelectClip={setSelectedClipId}
          onChanged={() => { if (selectedId) refreshDetail(selectedId); refreshProjects() }}
          onExportAll={() => refreshProjects()}
        />
      </div>
      <Toaster theme="dark" position="bottom-right" richColors />
    </div>
  )
}

function emptyDetail(id: string | null): ProjectDetail {
  return {
    id: id ?? "",
    name: "",
    source: "",
    source_size: 0,
    status: id ? "created" : "created",
    error: "",
    progress: 0,
    current_step: "",
    duration: 0,
    width: 0,
    height: 0,
    fps: 0,
    created_at: "",
    updated_at: "",
    steps: [],
    has_transcription: false,
    has_analysis: false,
    has_clips: false,
    clip_count: 0,
    transcription: null,
    analysis: null,
    content: null,
    clips: [],
    dirs: {},
  }
}
