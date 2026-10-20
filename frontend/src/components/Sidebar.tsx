import { useState, type FormEvent } from 'react'
import { Hash, Languages, LoaderCircle, MessagesSquare, Plus, Settings2, X } from 'lucide-react'
import { LANGUAGE_OPTIONS, useI18n } from '../i18n'
import type { Bot as BotType, Room, User } from '../types'
import { Avatar } from './Avatar'

type Props = {
  rooms: Room[]
  bots: BotType[]
  user: User | null
  selectedRoomId: string | null
  onSelect: (roomId: string) => void
  onCreateRoom: (payload: {
    name: string
    description: string
    bot_ids: string[]
  }) => Promise<void>
  onOpenSettings: () => void
  onNavigate: () => void
}

export function Sidebar({
  rooms,
  bots,
  user,
  selectedRoomId,
  onSelect,
  onCreateRoom,
  onOpenSettings,
  onNavigate,
}: Props) {
  const { language, setLanguage, t } = useI18n()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [botIds, setBotIds] = useState<string[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  const reset = () => {
    setName('')
    setDescription('')
    setBotIds([])
    setError('')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim() || pending) return
    setPending(true)
    setError('')
    try {
      await onCreateRoom({ name: name.trim(), description: description.trim(), bot_ids: botIds })
      setCreating(false)
      reset()
      onNavigate()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('sidebar.createRoomError'))
    } finally {
      setPending(false)
    }
  }

  return (
    <aside className="sidebar" aria-label={t('sidebar.rooms')}>
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <MessagesSquare size={18} strokeWidth={2} />
        </span>
        <div>
          <strong>AI Chat Room</strong>
          <span>{t('sidebar.subtitle')}</span>
        </div>
      </div>

      <div className="sidebar-heading">
        <span>{t('sidebar.rooms')}</span>
        <button
          type="button"
          className="icon-button"
          onClick={() => {
            setCreating((value) => !value)
            setError('')
          }}
          aria-label={creating ? t('sidebar.closeNewRoomForm') : t('sidebar.createRoom')}
          title={creating ? t('sidebar.close') : t('sidebar.createRoom')}
        >
          {creating ? <X size={17} /> : <Plus size={17} />}
        </button>
      </div>

      {creating && (
        <form className="stack-form room-form" onSubmit={submit}>
          <label>
            <span>{t('sidebar.roomName')}</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={80}
              placeholder={t('sidebar.roomNamePlaceholder')}
              autoFocus
              required
            />
          </label>
          <label>
            <span>{t('sidebar.description')}</span>
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={300}
              placeholder={t('sidebar.descriptionPlaceholder')}
            />
          </label>
          <fieldset>
            <legend>{t('sidebar.botsInRoom')}</legend>
            {bots.length === 0 ? (
              <p className="field-hint">{t('sidebar.createBotFirst')}</p>
            ) : (
              bots.map((bot) => (
                <label className="check-row" key={bot.id}>
                  <input
                    type="checkbox"
                    checked={botIds.includes(bot.id)}
                    onChange={() =>
                      setBotIds((current) =>
                        current.includes(bot.id)
                          ? current.filter((id) => id !== bot.id)
                          : [...current, bot.id],
                      )
                    }
                  />
                  <span>{bot.name}</span>
                </label>
              ))
            )}
          </fieldset>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button primary" disabled={pending || !name.trim()}>
            {pending && <LoaderCircle size={16} className="spin" />}
            {t('sidebar.createRoom')}
          </button>
        </form>
      )}

      <nav className="room-list" aria-label={t('sidebar.yourRooms')}>
        {rooms.length === 0 && !creating && (
          <div className="sidebar-empty">
            <Hash size={18} aria-hidden="true" />
            <p>{t('sidebar.noRooms')}</p>
            <button type="button" className="text-button" onClick={() => setCreating(true)}>
              {t('sidebar.createFirstRoom')}
            </button>
          </div>
        )}
        {rooms.map((room) => (
          <button
            type="button"
            key={room.id}
            className={`room-item ${room.id === selectedRoomId ? 'active' : ''}`}
            onClick={() => {
              onSelect(room.id)
              onNavigate()
            }}
            aria-current={room.id === selectedRoomId ? 'page' : undefined}
          >
            <span className="room-icon" aria-hidden="true">
              <Hash size={15} />
            </span>
            <span className="room-copy">
              <strong>{room.name}</strong>
              <span>{room.description || t('sidebar.noDescription')}</span>
            </span>
          </button>
        ))}
      </nav>

      <div className="sidebar-preferences">
        <label className="language-select" title={t('sidebar.language')}>
          <Languages size={14} aria-hidden="true" />
          <span>{t('sidebar.language')}</span>
          <select
            value={language}
            onChange={(event) => setLanguage(event.target.value === 'en' ? 'en' : 'zh')}
            aria-label={t('sidebar.language')}
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="sidebar-footer">
        {user ? (
          <>
            <Avatar name={user.display_name} kind="user" size="sm" />
            <div>
              <strong>{user.display_name}</strong>
              <span>{t('sidebar.presetAccount')}</span>
            </div>
          </>
        ) : (
          <span className="muted">{t('sidebar.connecting')}</span>
        )}
        <button
          type="button"
          className="icon-button settings-trigger"
          onClick={onOpenSettings}
          aria-label={t('sidebar.modelSettings')}
          title={t('sidebar.modelSettings')}
        >
          <Settings2 size={16} />
        </button>
      </div>
    </aside>
  )
}
