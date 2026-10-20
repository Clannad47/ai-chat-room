import { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Bot as BotIcon,
  LoaderCircle,
  Menu,
  MessagesSquare,
  PanelRight,
  Users,
} from 'lucide-react'
import { CONNECTION_MESSAGE_KEYS, STATUS_MESSAGE_KEYS, useI18n } from '../i18n'
import type { ConnectionState, Message, RoomDetail, Task } from '../types'
import { Avatar } from './Avatar'
import { Composer } from './Composer'

type Props = {
  room: RoomDetail | null
  messages: Message[]
  tasks: Task[]
  connection: ConnectionState
  loading: boolean
  onSend: (content: string) => Promise<void>
  onOpenSidebar: () => void
  onOpenInspector: () => void
}

export function ChatPanel({
  room,
  messages,
  tasks,
  connection,
  loading,
  onSend,
  onOpenSidebar,
  onOpenInspector,
}: Props) {
  const { locale, t } = useI18n()
  const listRef = useRef<HTMLDivElement>(null)
  const [stickToBottom, setStickToBottom] = useState(true)

  const working = tasks.filter((task) => task.status === 'queued' || task.status === 'running')

  useEffect(() => {
    if (!stickToBottom) return
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages.length, working.length, stickToBottom])

  if (!room) {
    return (
      <section className="chat-panel" aria-label={t('chat.ariaChat')}>
        {loading ? (
          <div className="workspace-loading" aria-live="polite">
            <LoaderCircle size={22} className="spin" aria-hidden="true" />
            <span>{t('chat.openingRoom')}</span>
            <div className="message-skeletons">
              <div className="skeleton skeleton-line short" />
              <div className="skeleton skeleton-block" />
              <div className="skeleton skeleton-line" />
            </div>
          </div>
        ) : (
          <div className="workspace-empty">
            <span className="empty-mark" aria-hidden="true">
              <MessagesSquare size={28} />
            </span>
            <h1>{t('chat.noRoomSelected')}</h1>
            <p>{t('chat.noRoomHint')}</p>
            <button type="button" className="button primary mobile-only" onClick={onOpenSidebar}>
              {t('chat.openRooms')}
            </button>
          </div>
        )}
      </section>
    )
  }

  return (
    <section className="chat-panel" aria-label={t('chat.chatIn', { name: room.name })}>
      <header className="chat-header">
        <button
          type="button"
          className="icon-button mobile-only"
          onClick={onOpenSidebar}
          aria-label={t('chat.openRooms')}
          title={t('chat.roomsTitle')}
        >
          <Menu size={18} />
        </button>
        <div className="room-title">
          <div>
            <h1>{room.name}</h1>
            <p>{room.description || t('chat.sharedRoom')}</p>
          </div>
        </div>
        <div className="header-meta">
          <span
            className="member-count"
            title={t('chat.botCountTitle', { count: room.bots.length })}
          >
            <Users size={15} aria-hidden="true" />
            {room.bots.length}{' '}
            {room.bots.length === 1
              ? t('chat.botCountSingular')
              : t('chat.botCountPlural')}
          </span>
          <span className={`connection-badge ${connection}`} aria-live="polite">
            <span className="connection-dot" aria-hidden="true" />
            {t(CONNECTION_MESSAGE_KEYS[connection])}
          </span>
          <button
            type="button"
            className="icon-button inspector-toggle"
            onClick={onOpenInspector}
            aria-label={t('chat.openRoomDetails')}
            title={t('chat.roomDetails')}
          >
            <PanelRight size={18} />
          </button>
        </div>
      </header>

      <div
        className="message-list"
        ref={listRef}
        onScroll={(event) => {
          const element = event.currentTarget
          setStickToBottom(element.scrollHeight - element.scrollTop - element.clientHeight < 140)
        }}
      >
        {loading && messages.length === 0 && (
          <div className="message-skeletons" aria-label={t('chat.loadingMessages')}>
            <div className="skeleton skeleton-line short" />
            <div className="skeleton skeleton-block" />
            <div className="skeleton skeleton-line" />
          </div>
        )}

        {!loading && messages.length === 0 && (
          <div className="message-empty">
            <span className="empty-mark" aria-hidden="true">
              <MessagesSquare size={24} />
            </span>
            <h2>{t('chat.startConversation')}</h2>
            <p>
              {room.bots.length > 0
                ? t('chat.startHintWithBots')
                : t('chat.startHintNoBots')}
            </p>
          </div>
        )}

        {messages.map((message) => {
          const isUser = message.sender_type === 'user'
          const task = message.task_id
            ? tasks.find((item) => item.id === message.task_id)
            : undefined
          return (
            <article key={message.id} className={`message ${isUser ? 'is-user' : 'is-bot'}`}>
              {!isUser && <Avatar name={message.sender_name} kind="bot" size="sm" />}
              <div className="message-body">
                <header>
                  <strong>{message.sender_name}</strong>
                  {message.sender_type === 'bot' && (
                    <span className="ai-chip">
                      <BotIcon size={11} aria-hidden="true" />
                      AI
                    </span>
                  )}
                  <time
                    dateTime={new Date(message.created_at).toISOString()}
                    title={new Date(message.created_at).toLocaleString(locale)}
                  >
                    {new Date(message.created_at).toLocaleTimeString(locale, {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </time>
                  {task && (
                    <span
                      className={`message-task ${task.status}`}
                      title={t('chat.taskTitle', {
                        status: t(STATUS_MESSAGE_KEYS[task.status]),
                      })}
                    >
                      {task.status === 'failed' && <AlertTriangle size={11} aria-hidden="true" />}
                      {t('chat.task')}
                    </span>
                  )}
                </header>
                <div className="bubble">
                  {message.content.split(/(@[\w\u4e00-\u9fff-]{1,32})/g).map((part, index) =>
                    part.startsWith('@') && message.mentions.some((m) => `@${m.name}` === part) ? (
                      <span className="mention-text" key={`${part}-${index}`}>
                        {part}
                      </span>
                    ) : (
                      part
                    ),
                  )}
                </div>
              </div>
              {isUser && <Avatar name={message.sender_name} kind="user" size="sm" />}
            </article>
          )
        })}

        {working.length > 0 && (
          <div className="working-row" aria-live="polite">
            <LoaderCircle size={15} className="spin" aria-hidden="true" />
            <span>
              {working.length === 1
                ? t('chat.workingOne', {
                    name:
                      room.bots.find((bot) => bot.id === working[0].assignee_bot_id)?.name ??
                      t('chat.aBot'),
                  })
                : t('chat.workingMany', { count: working.length })}
            </span>
          </div>
        )}
      </div>

      <Composer bots={room.bots} disabled={loading} onSend={onSend} />
    </section>
  )
}
