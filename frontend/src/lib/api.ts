import type {
  Clip,
  FeedbackRating,
  Project,
  ProjectDetail,
  SearchResult,
  Settings,
  SystemStatus,
} from "./types"

const BASE = "/api"

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init)
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail)
      if (body?.message) msg = body.message
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

// ---- projetos ----

export function listProjects(): Promise<Project[]> {
  return req("/projects")
}

export function getProject(id: string): Promise<ProjectDetail> {
  return req(`/projects/${id}`)
}

export function uploadVideo(file: File, onProgress?: (pct: number) => void): Promise<{ project: Project; upload_id: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${BASE}/projects`)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
    }
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText)
        if (xhr.status >= 200 && xhr.status < 300) resolve(body)
        else reject(new Error(body?.detail || `Erro ${xhr.status}`))
      } catch {
        reject(new Error("Resposta inválida do servidor"))
      }
    }
    xhr.onerror = () => reject(new Error("Falha no upload"))
    const fd = new FormData()
    fd.append("file", file)
    xhr.send(fd)
  })
}

export function importFromUrl(url: string): Promise<{ project: Project; upload_id: string }> {
  return req("/projects/import-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  })
}

export function processProject(id: string): Promise<{ ok: boolean; queued: boolean }> {
  return req(`/projects/${id}/process`, { method: "POST" })
}

export function cancelProject(id: string): Promise<{ ok: boolean }> {
  return req(`/projects/${id}/cancel`, { method: "POST" })
}

export function deleteProject(id: string): Promise<{ ok: boolean }> {
  return req(`/projects/${id}`, { method: "DELETE" })
}

export function searchTranscription(id: string, query: string): Promise<{ results: SearchResult[] }> {
  return req(`/projects/${id}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: 30 }),
  })
}

export function generateSubtitles(projectId: string): Promise<{ ok: boolean; files: Record<string, string> }> {
  return req(`/projects/${projectId}/subtitles`, { method: "POST" })
}

// ---- cortes ----

export function editClip(
  clipId: string,
  patch: Partial<{
    title: string
    caption: string
    description: string
    hashtags: string[]
    hook: string
    cta: string
    keywords: string[]
    source_start: number
    source_end: number
    feedback: string | null
  }>,
): Promise<Clip> {
  return req(`/clips/${clipId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  })
}

export function splitClip(clipId: string, at: number): Promise<Clip[]> {
  return req(`/clips/${clipId}/split`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ at }),
  })
}

export function mergeClips(clipId: string, otherClipId: string): Promise<Clip> {
  return req(`/clips/${clipId}/merge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ other_clip_id: otherClipId }),
  })
}

export function rateClip(clipId: string, rating: FeedbackRating): Promise<{ ok: boolean; feedback: string | null }> {
  return req(`/clips/${clipId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  })
}

export function regenerateText(clipId: string, field: string, promptHint = ""): Promise<Record<string, string>> {
  return req(`/clips/${clipId}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, prompt_hint: promptHint }),
  })
}

export function exportClip(clipId: string): Promise<{ clip_id: string; ok: boolean; path: string; error: string }> {
  return req(`/clips/${clipId}/export`, { method: "POST" })
}

export function exportAll(projectId: string, clipIds?: string[]): Promise<{ clip_id: string; ok: boolean; path: string; error: string }[]> {
  return req(`/clips/${projectId}/export-all`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clip_ids: clipIds }),
  })
}

// ---- sistema ----

export function getSettings(): Promise<Settings> {
  return req("/settings")
}

export function updateSettings(settings: Settings): Promise<Settings> {
  return req("/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ settings }),
  })
}

export function getSystemStatus(): Promise<SystemStatus> {
  return req("/system/status")
}

export function getAvailableModels(): Promise<{ models: string[] }> {
  return req("/system/models")
}

// ---- mídia ----

export function mediaUrl(absPath: string | undefined | null): string {
  if (!absPath) return ""
  const p = absPath.replace(/\\/g, "/")
  const marker = "/data/projects/"
  const idx = p.indexOf(marker)
  if (idx >= 0) return `/media/projects/${p.slice(idx + marker.length)}`
  const marker2 = "/projects/"
  const idx2 = p.indexOf(marker2)
  if (idx2 >= 0) return `/media${p.slice(idx2)}`
  return p
}

export function downloadUrl(absPath: string | undefined | null): string {
  const u = mediaUrl(absPath)
  return u || ""
}
