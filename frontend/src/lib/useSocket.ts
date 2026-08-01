import { useEffect, useRef } from "react"
import type { WsEvent } from "@/lib/types"

/**
 * Conecta ao WebSocket de um projeto e chama onEvent para cada evento.
 * Reconecta automaticamente em caso de falha.
 */
export function useProjectSocket(projectId: string | null, onEvent: (e: WsEvent) => void) {
  const cbRef = useRef(onEvent)
  cbRef.current = onEvent

  useEffect(() => {
    if (!projectId) return
    let ws: WebSocket | null = null
    let closed = false
    let retry: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      if (closed) return
      const proto = window.location.protocol === "https:" ? "wss" : "ws"
      ws = new WebSocket(`${proto}://${window.location.host}/api/ws/project/${projectId}`)
      ws.onmessage = (ev) => {
        try {
          cbRef.current(JSON.parse(ev.data) as WsEvent)
        } catch {
          /* ignore */
        }
      }
      ws.onclose = () => {
        if (!closed) retry = setTimeout(connect, 3000)
      }
      ws.onerror = () => ws?.close()
    }

    connect()
    return () => {
      closed = true
      if (retry) clearTimeout(retry)
      ws?.close()
    }
  }, [projectId])
}
