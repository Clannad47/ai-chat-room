import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, LoaderCircle, MessagesSquare, RefreshCw, X } from 'lucide-react'
import { api } from './api'
import './App.css'
import { ChatPanel } from './components/ChatPanel'
import { Inspector } from './components/Inspector'
import { ModelSettings } from './components/ModelSettings'
import { Sidebar } from './components/Sidebar'
import type {
  Bot,
  ConnectionState,
  Message,
  Room,
  RoomDetail,
  Task,
  TaskDetail,
  User,
  WsEvent,
} from './types'
import { useI18n } from './i18n'
import { mergeMessages, upsertTask } from './utils'
import { useRoomSocket } from './useRoomSocket'

function App() {
  const { t } = useI18n()
  const [me, setMe] = useState<User | null>(null)
  const [bots, setBots] = useState<Bot[]>([])
  const [rooms, setRooms] = useState<Room[]>([])
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null)
  const [room, setRoom] = useState<RoomDetail | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null)
  const [taskLoading, setTaskLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [roomLoading, setRoomLoading] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const selectedRoomRef = useRef<string | null>(null)
  const selectedTaskIdRef = useRef<string | null>(null)
  const tRef = useRef(t)

  useEffect(() => {
    tRef.current = t
  }, [t])

  useEffect(() => {
    selectedRoomRef.current = selectedRoomId
  }, [selectedRoomId])

  useEffect(() => {
    selectedTaskIdRef.current = selectedTask?.id ?? null
  }, [selectedTask])

  const loadInitial = useCallback(async () => {
    setInitialLoading(true)
    setError('')
    try {
      const [user, botList, roomList] = await Promise.all([
        api.me(),
        api.listBots(),
        api.listRooms(),
      ])
      setMe(user)
      setBots(botList)
      setRooms(roomList)
      setSelectedRoomId((current) => {
        if (current && roomList.some((item) => item.id === current)) return current
        const hashId = window.location.hash.match(/^#\/rooms\/([0-9a-f-]{36})/i)?.[1]
        return roomList.find((item) => item.id === hashId)?.id ?? roomList[0]?.id ?? null
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : tRef.current('app.loadWorkspaceError'))
    } finally {
      setInitialLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadInitial()
  }, [loadInitial])

  useEffect(() => {
    const onHashChange = () => {
      const hashId = window.location.hash.match(/^#\/rooms\/([0-9a-f-]{36})/i)?.[1]
      if (hashId && rooms.some((item) => item.id === hashId)) setSelectedRoomId(hashId)
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [rooms])

  const refreshRoom = useCallback(async (roomId: string, quiet = false) => {
    if (!quiet) setRoomLoading(true)
    try {
      const [detail, messageList, taskList] = await Promise.all([
        api.getRoom(roomId),
        api.listMessages(roomId),
        api.listTasks(roomId),
      ])
      if (selectedRoomRef.current !== roomId) return
      setRoom(detail)
      setMessages((current) => mergeMessages(current, messageList))
      setTasks(taskList)
      setRooms((current) =>
        current.map((item) =>
          item.id === roomId
            ? {
                ...item,
                name: detail.name,
                description: detail.description,
                next_seq: detail.next_seq,
              }
            : item,
        ),
      )
    } catch (caught) {
      if (selectedRoomRef.current === roomId) {
        setError(caught instanceof Error ? caught.message : tRef.current('app.loadRoomError'))
      }
    } finally {
      if (!quiet && selectedRoomRef.current === roomId) setRoomLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!selectedRoomId) {
      setRoom(null)
      setMessages([])
      setTasks([])
      setSelectedTask(null)
      setRoomLoading(false)
      return
    }

    let active = true
    setRoom(null)
    setMessages([])
    setTasks([])
    setSelectedTask(null)
    setRoomLoading(true)
    setError('')

    void (async () => {
      try {
        const [detail, messageList, taskList] = await Promise.all([
          api.getRoom(selectedRoomId),
          api.listMessages(selectedRoomId),
          api.listTasks(selectedRoomId),
        ])
        if (!active) return
        setRoom(detail)
        setMessages((current) => mergeMessages(current, messageList))
        setTasks(taskList)
      } catch (caught) {
        if (active) {
          setError(caught instanceof Error ? caught.message : tRef.current('app.loadRoomError'))
        }
      } finally {
        if (active) setRoomLoading(false)
      }
    })()

    return () => {
      active = false
    }
  }, [selectedRoomId])

  const onSocketEvent = useCallback((event: WsEvent) => {
    if (event.type === 'message.created') {
      const message = event.payload.message as Message | undefined
      if (message && message.room_id === selectedRoomRef.current) {
        setMessages((current) => mergeMessages(current, [message]))
      }
      return
    }
    if (event.type === 'task.updated') {
      const task = event.payload.task as Task | undefined
      if (!task || task.room_id !== selectedRoomRef.current) return
      setTasks((current) => upsertTask(current, task))
      if (selectedTaskIdRef.current === task.id) {
        void api.getTask(task.id).then(setSelectedTask).catch(() => undefined)
      }
    }
  }, [])

  const onSocketOpen = useCallback(() => {
    const roomId = selectedRoomRef.current
    if (roomId) void refreshRoom(roomId, true)
  }, [refreshRoom])

  const connection: ConnectionState = useRoomSocket(
    selectedRoomId,
    onSocketEvent,
    onSocketOpen,
  )

  const selectRoom = (roomId: string) => {
    if (roomId === selectedRoomId) {
      setSidebarOpen(false)
      return
    }
    setSelectedRoomId(roomId)
    history.replaceState(null, '', `#/rooms/${roomId}`)
    setSidebarOpen(false)
    setInspectorOpen(false)
  }

  const createRoom = async (payload: {
    name: string
    description: string
    bot_ids: string[]
  }) => {
    const detail = await api.createRoom(payload)
    setRooms((current) => [detail, ...current])
    setRoom(detail)
    history.replaceState(null, '', `#/rooms/${detail.id}`)
    setSelectedRoomId(detail.id)
    setSidebarOpen(false)
  }

  const sendMessage = async (content: string) => {
    if (!selectedRoomId) throw new Error(t('app.selectRoomFirst'))
    const message = await api.sendMessage(selectedRoomId, content)
    setMessages((current) => mergeMessages(current, [message]))
  }

  const createBot = async (payload: {
    name: string
    description: string
    persona: string
    model?: string | null
    allowed_tools: string[]
    max_steps?: number
  }) => {
    const bot = await api.createBot(payload)
    setBots((current) => [...current, bot])
    if (selectedRoomId) {
      const detail = await api.addBot(selectedRoomId, bot.id)
      setRoom(detail)
    }
  }

  const addBot = async (botId: string) => {
    if (!selectedRoomId) return
    const detail = await api.addBot(selectedRoomId, botId)
    setRoom(detail)
  }

  const removeBot = async (botId: string) => {
    if (!selectedRoomId) return
    const detail = await api.removeBot(selectedRoomId, botId)
    setRoom(detail)
  }

  const selectTask = async (taskId: string) => {
    setTaskLoading(true)
    setSelectedTask(null)
    try {
      setSelectedTask(await api.getTask(taskId))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('app.loadTaskError'))
    } finally {
      setTaskLoading(false)
    }
  }

  const cancelTask = async (taskId: string) => {
    const task = await api.cancelTask(taskId)
    setTasks((current) => upsertTask(current, task))
    setSelectedTask(await api.getTask(taskId))
  }

  if (initialLoading) {
    return (
      <div className="app-loading" aria-live="polite">
        <span className="brand-mark" aria-hidden="true">
          <MessagesSquare size={20} />
        </span>
        <LoaderCircle size={18} className="spin" aria-hidden="true" />
        <span>{t('app.loadingWorkspace')}</span>
      </div>
    )
  }

  return (
    <div
      className={`app-shell ${sidebarOpen ? 'show-sidebar' : ''} ${
        inspectorOpen ? 'show-inspector' : ''
      }`}
    >
      <button
        type="button"
        className="drawer-backdrop"
        aria-label={t('app.closePanels')}
        onClick={() => {
          setSidebarOpen(false)
          setInspectorOpen(false)
        }}
      />

      <Sidebar
        rooms={rooms}
        bots={bots}
        user={me}
        selectedRoomId={selectedRoomId}
        onSelect={selectRoom}
        onCreateRoom={createRoom}
        onOpenSettings={() => setSettingsOpen(true)}
        onNavigate={() => setSidebarOpen(false)}
      />

      <ChatPanel
        room={room}
        messages={messages}
        tasks={tasks}
        connection={connection}
        loading={roomLoading}
        onSend={sendMessage}
        onOpenSidebar={() => setSidebarOpen(true)}
        onOpenInspector={() => setInspectorOpen(true)}
      />

      {settingsOpen && <ModelSettings onClose={() => setSettingsOpen(false)} />}

      <Inspector
        room={room}
        allBots={bots}
        tasks={tasks}
        selectedTask={selectedTask}
        taskLoading={taskLoading}
        onClose={() => setInspectorOpen(false)}
        onAddBot={addBot}
        onRemoveBot={removeBot}
        onCreateBot={createBot}
        onSelectTask={selectTask}
        onBackToTasks={() => setSelectedTask(null)}
        onCancelTask={cancelTask}
      />

      {error && (
        <div className="app-banner" role="alert">
          <AlertTriangle size={16} aria-hidden="true" />
          <span>{error}</span>
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setError('')
              void loadInitial()
              if (selectedRoomRef.current) void refreshRoom(selectedRoomRef.current)
            }}
          >
            <RefreshCw size={14} aria-hidden="true" />
            {t('app.retry')}
          </button>
          <button
            type="button"
            className="icon-button subtle"
            onClick={() => setError('')}
            aria-label={t('app.dismissError')}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  )
}

export default App
