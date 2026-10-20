import type { Message, Task } from './types'

export function mergeMessages(existing: Message[], incoming: Message[]): Message[] {
  const byId = new Map(existing.map((message) => [message.id, message]))
  for (const message of incoming) byId.set(message.id, message)
  return [...byId.values()]
    .sort((a, b) => a.seq - b.seq)
    .slice(-300)
}

export function upsertTask(tasks: Task[], task: Task): Task[] {
  const byId = new Map(tasks.map((item) => [item.id, item]))
  byId.set(task.id, task)
  return [...byId.values()].sort((a, b) => b.created_at - a.created_at)
}
