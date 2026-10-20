export type User = {
  id: string
  username: string
  display_name: string
}

export type Bot = {
  id: string
  name: string
  description: string
  persona: string
  model: string | null
  temperature: number
  allowed_tools: string[]
  max_steps: number
  created_at: number
}

export type LLMSettings = {
  provider: string
  model: string
  base_url: string | null
  api_key_set: boolean
  api_key_hint: string | null
  updated_at: number
}

export type LLMSettingsUpdate = {
  provider?: string
  model: string
  base_url?: string | null
  api_key?: string
  clear_api_key?: boolean
}

export type Room = {
  id: string
  name: string
  description: string
  next_seq: number
  created_at: number
}

export type RoomDetail = Room & {
  bots: Bot[]
  tasks_pending: number
}

export type Mention = {
  type: 'bot' | 'user'
  id: string
  name: string
}

export type Message = {
  id: string
  room_id: string
  seq: number
  sender_type: 'user' | 'bot' | 'system'
  sender_id: string | null
  sender_name: string
  content: string
  mentions: Mention[]
  task_id: string | null
  origin_run_id: string | null
  created_at: number
}

export type TaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export type Task = {
  id: string
  room_id: string
  root_id: string
  parent_id: string | null
  assignee_bot_id: string
  trigger_message_id: string
  goal: string
  depth: number
  status: TaskStatus
  result_message_id: string | null
  error: string | null
  created_at: number
  started_at: number | null
  finished_at: number | null
}

export type ToolCall = {
  id: string
  name: string
  arguments: Record<string, unknown>
  result_preview: string
  status: string
  error: string | null
  created_at: number
  finished_at: number | null
}

export type Run = {
  id: string
  task_id: string
  bot_id: string
  attempt: number
  status: 'running' | 'succeeded' | 'failed' | 'cancelled'
  model: string
  input_tokens: number
  output_tokens: number
  error: string | null
  created_at: number
  finished_at: number | null
  tool_calls: ToolCall[]
}

export type TaskDetail = Task & {
  assignee_name: string
  runs: Run[]
}

export type WsEvent = {
  type: string
  room_id: string
  seq: number | null
  payload: Record<string, unknown>
  ts: number
}

export type ConnectionState = 'connecting' | 'live' | 'reconnecting' | 'offline'
