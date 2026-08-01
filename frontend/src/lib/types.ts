export interface WordTS {
  word: string
  start: number
  end: number
  probability: number
}

export interface Segment {
  id: number
  start: number
  end: number
  text: string
  words: WordTS[]
}

export interface Transcription {
  language: string
  duration: number
  segments: Segment[]
}

export interface Scene {
  start: number
  end: number
}

export interface Silence {
  start: number
  end: number
  duration: number
}

export interface SentenceSignal {
  sentence_index: number
  start: number
  end: number
  energy: number
  pace: number
  intensity: number
  emotion_score: number
  text: string
}

export interface Analysis {
  scenes: Scene[]
  silences: Silence[]
  sentence_signals: SentenceSignal[]
}

export interface Highlight {
  sentence_start: number
  sentence_end: number
  types: string[]
  score: number
  reason: string
  retention: number
  virality: number
  educational: number
  sharing: number
  emotion: number
  clarity: number
  duration_pref: number
}

export interface ContentAnalysis {
  summary: string
  themes: string[]
  highlights: Highlight[]
  hook_lines: string[]
  cta_lines: string[]
}

export interface ClipScores {
  retention: number
  virality: number
  educational: number
  sharing: number
  emotion: number
  clarity: number
}

export interface ClipFiles {
  video: string
  subtitle: string
  subtitle_ass: string
  thumbnail: string
  preview: string
}

export interface Clip {
  id: string
  project_id: string
  source_start: number
  source_end: number
  duration: number
  title: string
  caption: string
  description: string
  hashtags: string[]
  hook: string
  cta: string
  keywords: string[]
  tags: string[]
  scores: ClipScores
  total_score: number
  feedback: string | null
  files: ClipFiles
  transcript_excerpt: string
  created_at: string
}

export interface PipelineStep {
  id: string
  label: string
  status: string
  progress: number
  detail: string
}

export type ProjectStatus =
  | "created"
  | "ready"
  | "processing"
  | "error"
  | "queued"
  | "downloading"

export interface Project {
  id: string
  name: string
  source: string
  source_size: number
  status: ProjectStatus
  error: string
  progress: number
  current_step: string
  duration: number
  width: number
  height: number
  fps: number
  created_at: string
  updated_at: string
  steps: PipelineStep[]
  has_transcription: boolean
  has_analysis: boolean
  has_clips: boolean
  clip_count: number
}

export interface ProjectDetail extends Project {
  transcription: Transcription | null
  analysis: Analysis | null
  content: ContentAnalysis | null
  clips: Clip[]
  dirs: Record<string, string>
}

export interface Settings {
  whisper_model: string
  whisper_device: string
  whisper_compute: string
  language: string
  ai_provider: string
  ai_model: string
  ai_base_url: string
  ai_temperature: number
  min_clip_duration: number
  max_clip_duration: number
  clip_durations: number[]
  subtitle_style: {
    style: string
    font: string
    font_size: number
    color: string
    outline_color: string
    outline_width: number
    shadow: boolean
    shadow_color: string
    position: string
    animation: string
    words_per_line: number
  }
  export_quality: string
  use_gpu: boolean
  max_clips: number
  download_subtitles: boolean
  face_detection: boolean
}

export interface SystemStatus {
  cuda_available: boolean
  ai_provider: string
  ai_model: string
  ai_ok: boolean
  ai_message: string
  queue: { current: string | null; pending: string[] }
  learning: {
    total_feedback: number
    preferred_duration: number
    preferred_tags: string[]
  }
}

export interface SearchResult {
  index: number
  start: number
  end: number
  text: string
}

export type FeedbackRating = "excellent" | "good" | "bad" | "ignore" | "none"

export interface WsEvent {
  type: string
  step?: string
  status?: string
  progress?: number
  detail?: string
  message?: string
  project?: Project
}
