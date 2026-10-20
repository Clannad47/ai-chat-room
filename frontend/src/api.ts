import type {
  Bot,
  LLMSettings,
  LLMSettingsUpdate,
  Message,
  Room,
  RoomDetail,
  Task,
  TaskDetail,
  User,
} from './types'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`/api${path}`, { ...init, headers })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail) detail = JSON.stringify(body.detail)
    } catch {
      // Keep the status-based message.
    }
    throw new ApiError(detail, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  me: () => request<User>('/me'),
  getLLMSettings: () => request<LLMSettings>('/settings/llm'),
  updateLLMSettings: (payload: LLMSettingsUpdate) =>
    request<LLMSettings>('/settings/llm', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  listBots: () => request<Bot[]>('/bots'),
  createBot: (payload: {
    name: string
    description: string
    persona: string
    model?: string | null
    allowed_tools: string[]
    max_steps?: number
  }) =>
    request<Bot>('/bots', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  listRooms: () => request<Room[]>('/rooms'),
  createRoom: (payload: { name: string; description: string; bot_ids: string[] }) =>
    request<RoomDetail>('/rooms', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getRoom: (roomId: string) => request<RoomDetail>(`/rooms/${roomId}`),
  addBot: (roomId: string, botId: string) =>
    request<RoomDetail>(`/rooms/${roomId}/bots/${botId}`, { method: 'POST' }),
  removeBot: (roomId: string, botId: string) =>
    request<RoomDetail>(`/rooms/${roomId}/bots/${botId}`, { method: 'DELETE' }),
  listMessages: (roomId: string, limit = 100) =>
    request<Message[]>(`/rooms/${roomId}/messages?limit=${limit}`),
  sendMessage: (roomId: string, content: string) =>
    request<Message>(`/rooms/${roomId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
  listTasks: (roomId: string) => request<Task[]>(`/rooms/${roomId}/tasks`),
  getTask: (taskId: string) => request<TaskDetail>(`/tasks/${taskId}`),
  cancelTask: (taskId: string) =>
    request<Task>(`/tasks/${taskId}/cancel`, { method: 'POST' }),
}
