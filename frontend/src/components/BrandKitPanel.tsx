import { useRef, useState } from "react"
import { Loader2, Upload, X } from "lucide-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { uploadLogo } from "@/lib/api"
import { mediaUrl } from "@/lib/api"
import type { Settings } from "@/lib/types"

const LOGO_POSITIONS = [
  ["top-left", "Superior esquerda"],
  ["top-right", "Superior direita"],
  ["bottom-left", "Inferior esquerda"],
  ["bottom-right", "Inferior direita"],
] as const

const FONTS = [
  "Arial",
  "Arial Black",
  "Helvetica",
  "Montserrat",
  "Montserrat ExtraBold",
  "Poppins",
  "Roboto",
  "Segoe UI",
  "Segoe UI Light",
  "Verdana",
  "Comic Sans MS",
  "Impact",
] as const

export function BrandKitPanel({
  settings,
  set,
}: {
  settings: Settings
  set: (patch: Partial<Settings>) => void
}) {
  const [uploading, setUploading] = useState(false)
  const logoInputRef = useRef<HTMLInputElement>(null)
  const bk = settings.brand_kit
  const patch = (p: Partial<Settings["brand_kit"]>) => set({ brand_kit: { ...bk, ...p } })

  const onLogo = async (file: File | undefined) => {
    if (!file) return
    setUploading(true)
    try {
      const res = await uploadLogo(file)
      patch({ logo_path: res.path, use_logo: true })
      toast.success("Logo enviado")
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Falha ao enviar logo")
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-semibold text-muted-foreground">Identidade visual (Brand Kit)</p>

      <div className="flex items-start gap-3">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-border bg-muted/40">
          {bk.logo_path ? (
            <img src={mediaUrl(bk.logo_path)} alt="Logo" className="h-full w-full object-contain" />
          ) : (
            <span className="text-2xs text-muted-foreground">Logo</span>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <input
            ref={logoInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => { void onLogo(e.target.files?.[0]); e.target.value = "" }}
          />
          <div className="flex gap-1">
            <Button size="xs" variant="outline" disabled={uploading} onClick={() => logoInputRef.current?.click()}>
              {uploading ? <Loader2 className="animate-spin" /> : <Upload />}
              Enviar logo
            </Button>
            {bk.logo_path && (
              <Button size="xs" variant="ghost" title="Remover logo" onClick={() => patch({ logo_path: "", use_logo: false })}>
                <X />
              </Button>
            )}
          </div>
          <span className="text-[11px] text-muted-foreground">PNG/JPEG com transparência, idealmente ≤ 200px de largura.</span>
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 accent-[var(--primary)]"
          checked={bk.use_logo}
          onChange={(e) => patch({ use_logo: e.target.checked })}
        />
        Usar logo da marca no vídeo
      </label>

      {bk.use_logo && (
        <div className="flex items-center gap-2">
          <label className="w-32 shrink-0 text-muted-foreground">Posição do logo</label>
          <select
            className="h-8 flex-1 rounded-md border border-input bg-background px-2"
            value={bk.logo_position}
            onChange={(e) => patch({ logo_position: e.target.value as Settings["brand_kit"]["logo_position"] })}
          >
            {LOGO_POSITIONS.map(([v, label]) => (
              <option key={v} value={v}>{label}</option>
            ))}
          </select>
        </div>
      )}

      <div className="flex items-center gap-2">
        <label className="w-32 shrink-0 text-muted-foreground">Cor primária</label>
        <input
          type="color"
          value={bk.primary_color}
          onChange={(e) => patch({ primary_color: e.target.value })}
          className="h-8 w-14 cursor-pointer rounded border border-input bg-background"
        />
        <Input value={bk.primary_color} onChange={(e) => patch({ primary_color: e.target.value })} className="h-8 flex-1" />
      </div>
      <div className="flex items-center gap-2">
        <label className="w-32 shrink-0 text-muted-foreground">Cor secundária</label>
        <input
          type="color"
          value={bk.secondary_color}
          onChange={(e) => patch({ secondary_color: e.target.value })}
          className="h-8 w-14 cursor-pointer rounded border border-input bg-background"
        />
        <Input value={bk.secondary_color} onChange={(e) => patch({ secondary_color: e.target.value })} className="h-8 flex-1" />
      </div>

      <div className="flex items-center gap-2">
        <label className="w-32 shrink-0 text-muted-foreground">Fonte da marca</label>
        <select
          className="h-8 flex-1 rounded-md border border-input bg-background px-2"
          value={bk.font_family || "Arial Black"}
          onChange={(e) => patch({ font_family: e.target.value })}
        >
          {FONTS.map((f) => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-4 w-4 accent-[var(--primary)]"
          checked={bk.use_brand_font}
          onChange={(e) => patch({ use_brand_font: e.target.checked })}
        />
        Usar fonte da marca nas legendas
      </label>
    </div>
  )
}