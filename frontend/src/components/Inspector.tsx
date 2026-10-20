import { useState, type FormEvent } from 'react'
import {
  AlertTriangle,
  Bot as BotIcon,
  CheckCircle2,
  ChevronLeft,
  CircleSlash,
  Clock3,
  LoaderCircle,
  Plus,
  Trash2,
  Wrench,
  X,
} from 'lucide-react'
import { STATUS_MESSAGE_KEYS, useI18n, type MessageKey } from '../i18n'
import type { Bot, RoomDetail, Task, TaskDetail } from '../types'
import { Avatar } from './Avatar'

const TOOL_OPTIONS: { name: string; labelKey: MessageKey; hintKey: MessageKey }[] = [
  {
    name: 'get_room_history',
    labelKey: 'tools.getRoomHistory.label',
    hintKey: 'tools.getRoomHistory.hint',
  },
  {
    name: 'delegate_to_bot',
    labelKey: 'tools.delegateToBot.label',
    hintKey: 'tools.delegateToBot.hint',
  },
  {
    name: 'fetch_url',
    labelKey: 'tools.fetchUrl.label',
    hintKey: 'tools.fetchUrl.hint',
  },
]

function StatusBadge({ status }: { status: Task['status'] }) {
  const { t } = useI18n()
  const Icon =
    status === 'failed'
      ? AlertTriangle
      : status === 'succeeded'
        ? CheckCircle2
        : status === 'cancelled'
          ? CircleSlash
          : status === 'running'
            ? LoaderCircle
            : Clock3
  return (
    <span className={`status-badge ${status}`}>
      <Icon size={12} className={status === 'running' ? 'spin' : undefined} aria-hidden="true" />
      {t(STATUS_MESSAGE_KEYS[status])}
    </span>
  )
}

type Props = {
  room: RoomDetail | null
  allBots: Bot[]
  tasks: Task[]
  selectedTask: TaskDetail | null
  taskLoading: boolean
  onClose: () => void
  onAddBot: (botId: string) => Promise<void>
  onRemoveBot: (botId: string) => Promise<void>
  onCreateBot: (payload: {
    name: string
    description: string
    persona: string
    model?: string | null
    allowed_tools: string[]
    max_steps?: number
  }) => Promise<void>
  onSelectTask: (taskId: string) => void
  onBackToTasks: () => void
  onCancelTask: (taskId: string) => Promise<void>
}

export function Inspector({
  room,
  allBots,
  tasks,
  selectedTask,
  taskLoading,
  onClose,
  onAddBot,
  onRemoveBot,
  onCreateBot,
  onSelectTask,
  onBackToTasks,
  onCancelTask,
}: Props) {
  const { locale, t } = useI18n()
  const [tab, setTab] = useState<'agents' | 'tasks'>('agents')
  const [addId, setAddId] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [showBotForm, setShowBotForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [persona, setPersona] = useState('')
  const [model, setModel] = useState('')
  const [tools, setTools] = useState(TOOL_OPTIONS.map((tool) => tool.name))

  const availableBots = allBots.filter(
    (bot) => !room?.bots.some((member) => member.id === bot.id),
  )
  const activeTab = selectedTask ? 'tasks' : tab

  const runAction = async (key: string, action: () => Promise<void>) => {
    setBusy(key)
    setError('')
    try {
      await action()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('inspector.actionFailed'))
    } finally {
      setBusy('')
    }
  }

  const submitBot = async (event: FormEvent) => {
    event.preventDefault()
    if (!name.trim()) return
    await runAction('create', async () => {
      await onCreateBot({
        name: name.trim(),
        description: description.trim(),
        persona: persona.trim(),
        model: model.trim() || null,
        allowed_tools: tools,
      })
      setShowBotForm(false)
      setName('')
      setDescription('')
      setPersona('')
      setModel('')
      setTools(TOOL_OPTIONS.map((tool) => tool.name))
    })
  }

  return (
    <aside className="inspector" aria-label={t('chat.roomDetails')}>
      <header className="inspector-header">
        <div className="tabs" role="tablist" aria-label={t('inspector.sections')}>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'agents'}
            className={activeTab === 'agents' ? 'active' : ''}
            onClick={() => {
              setTab('agents')
              onBackToTasks()
            }}
          >
            {t('inspector.agentsTab')}
            <span>{room?.bots.length ?? 0}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'tasks'}
            className={activeTab === 'tasks' ? 'active' : ''}
            onClick={() => setTab('tasks')}
          >
            {t('inspector.tasksTab')}
            <span>{tasks.length}</span>
          </button>
        </div>
        <button
          type="button"
          className="icon-button inspector-close"
          onClick={onClose}
          aria-label={t('inspector.closeRoomDetails')}
          title={t('sidebar.close')}
        >
          <X size={17} />
        </button>
      </header>

      {error && (
        <p className="form-error inspector-error" role="alert">
          {error}
        </p>
      )}

      {activeTab === 'agents' && (
        <div className="inspector-body">
          <section className="inspector-section">
            <div className="section-heading">
              <div>
                <h2>{t('inspector.roomAgents')}</h2>
                <p>{t('inspector.roomAgentsHint')}</p>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowBotForm((value) => !value)}
                aria-label={
                  showBotForm ? t('inspector.closeBotForm') : t('inspector.createBot')
                }
                title={showBotForm ? t('sidebar.close') : t('inspector.createBot')}
              >
                {showBotForm ? <X size={16} /> : <Plus size={16} />}
              </button>
            </div>

            {showBotForm && (
              <form className="stack-form bot-form" onSubmit={submitBot}>
                <label>
                  <span>{t('inspector.name')}</span>
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder={t('inspector.namePlaceholder')}
                    maxLength={32}
                    pattern="[\w\-\u4e00-\u9fff]{1,32}"
                    autoFocus
                    required
                  />
                  <small>{t('inspector.nameHint')}</small>
                </label>
                <label>
                  <span>{t('inspector.description')}</span>
                  <input
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder={t('inspector.descriptionPlaceholder')}
                    maxLength={200}
                  />
                </label>
                <label>
                  <span>{t('inspector.persona')}</span>
                  <textarea
                    value={persona}
                    onChange={(event) => setPersona(event.target.value)}
                    placeholder={t('inspector.personaPlaceholder')}
                    rows={3}
                    maxLength={4000}
                  />
                </label>
                <label>
                  <span>{t('inspector.modelOverride')}</span>
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    placeholder={t('inspector.defaultModel')}
                    maxLength={100}
                  />
                </label>
                <fieldset>
                  <legend>{t('inspector.tools')}</legend>
                  {TOOL_OPTIONS.map((tool) => (
                    <label className="check-row" key={tool.name}>
                      <input
                        type="checkbox"
                        checked={tools.includes(tool.name)}
                        onChange={() =>
                          setTools((current) =>
                            current.includes(tool.name)
                              ? current.filter((item) => item !== tool.name)
                              : [...current, tool.name],
                          )
                        }
                      />
                      <span>
                        {t(tool.labelKey)}
                        <small>{t(tool.hintKey)}</small>
                      </span>
                    </label>
                  ))}
                </fieldset>
                <button
                  type="submit"
                  className="button primary"
                  disabled={busy === 'create' || !name.trim()}
                >
                  {busy === 'create' && <LoaderCircle size={16} className="spin" />}
                  {t('inspector.createBot')}
                </button>
              </form>
            )}

            <div className="agent-list">
              {room?.bots.length === 0 && (
                <div className="panel-empty">
                  <BotIcon size={20} aria-hidden="true" />
                  <p>{t('inspector.noBots')}</p>
                </div>
              )}
              {room?.bots.map((bot) => (
                <div className="agent-row" key={bot.id}>
                  <Avatar name={bot.name} kind="bot" size="sm" />
                  <div className="agent-copy">
                    <strong>{bot.name}</strong>
                    <span>{bot.description || t('inspector.aiCollaborator')}</span>
                    <div className="tool-chips">
                      <Wrench size={11} aria-hidden="true" />
                      {t('inspector.toolCount', { count: bot.allowed_tools.length })}
                      {bot.model && <em>{bot.model}</em>}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="icon-button subtle"
                    onClick={() => void runAction(`remove-${bot.id}`, () => onRemoveBot(bot.id))}
                    disabled={busy === `remove-${bot.id}`}
                    aria-label={t('inspector.removeBot', { name: bot.name })}
                    title={t('inspector.removeFromRoom')}
                  >
                    {busy === `remove-${bot.id}` ? (
                      <LoaderCircle size={15} className="spin" />
                    ) : (
                      <Trash2 size={15} />
                    )}
                  </button>
                </div>
              ))}
            </div>

            {availableBots.length > 0 && room && (
              <div className="add-agent">
                <label htmlFor="add-agent-select">{t('inspector.addExistingBot')}</label>
                <div className="inline-control">
                  <select
                    id="add-agent-select"
                    value={addId}
                    onChange={(event) => setAddId(event.target.value)}
                  >
                    <option value="">{t('inspector.chooseBot')}</option>
                    {availableBots.map((bot) => (
                      <option key={bot.id} value={bot.id}>
                        {bot.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="button secondary"
                    disabled={!addId || busy === 'add'}
                    onClick={() =>
                      void runAction('add', async () => {
                        await onAddBot(addId)
                        setAddId('')
                      })
                    }
                  >
                    {busy === 'add' ? <LoaderCircle size={16} className="spin" /> : <Plus size={16} />}
                    {t('inspector.add')}
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === 'tasks' && (
        <div className="inspector-body">
          {selectedTask || taskLoading ? (
            taskLoading ? (
              <div className="task-detail-loading">
                <div className="skeleton skeleton-line" />
                <div className="skeleton skeleton-block" />
              </div>
            ) : (
              selectedTask && (
                <section className="task-detail">
                  <button type="button" className="back-button" onClick={onBackToTasks}>
                    <ChevronLeft size={15} />
                    {t('inspector.allTasks')}
                  </button>
                  <div className="task-detail-heading">
                    <div>
                      <span className="eyebrow">{t('inspector.taskEyebrow')}</span>
                      <h2>{selectedTask.assignee_name}</h2>
                    </div>
                    <StatusBadge status={selectedTask.status} />
                  </div>
                  <p className="task-goal">{selectedTask.goal}</p>
                  <dl className="task-facts">
                    <div>
                      <dt>{t('inspector.depth')}</dt>
                      <dd>{selectedTask.depth}</dd>
                    </div>
                    <div>
                      <dt>{t('inspector.created')}</dt>
                      <dd>{new Date(selectedTask.created_at).toLocaleString(locale)}</dd>
                    </div>
                    <div>
                      <dt>{t('inspector.taskId')}</dt>
                      <dd className="mono">{selectedTask.id.slice(0, 8)}</dd>
                    </div>
                  </dl>
                  {selectedTask.error && (
                    <p className="task-error" role="alert">
                      <AlertTriangle size={14} aria-hidden="true" />
                      {selectedTask.error}
                    </p>
                  )}
                  {(selectedTask.status === 'queued' || selectedTask.status === 'running') && (
                    <button
                      type="button"
                      className="button danger"
                      disabled={busy === 'cancel'}
                      onClick={() =>
                        void runAction('cancel', () => onCancelTask(selectedTask.id))
                      }
                    >
                      {busy === 'cancel' ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <CircleSlash size={16} />
                      )}
                      {t('inspector.cancelTask')}
                    </button>
                  )}
                  <div className="runs">
                    <h3>{t('inspector.runs')}</h3>
                    {selectedTask.runs.length === 0 && (
                      <p className="muted">{t('inspector.noRun')}</p>
                    )}
                    {selectedTask.runs.map((run) => (
                      <details className="run-card" key={run.id} open>
                        <summary>
                          <span>{t('inspector.attempt', { count: run.attempt })}</span>
                          <span className="mono">{run.model}</span>
                          <StatusBadge status={run.status} />
                        </summary>
                        <div className="run-meta">
                          <span>{t('inspector.inputTokens', { count: run.input_tokens })}</span>
                          <span>{t('inspector.outputTokens', { count: run.output_tokens })}</span>
                          {run.error && <span className="danger-text">{run.error}</span>}
                        </div>
                        {run.tool_calls.map((call) => (
                          <details className="tool-call" key={call.id}>
                            <summary>
                              <Wrench size={13} aria-hidden="true" />
                              {call.name}
                              <span className={`tool-status ${call.status}`}>{call.status}</span>
                            </summary>
                            <pre>{JSON.stringify(call.arguments, null, 2)}</pre>
                            <p>{call.result_preview || t('inspector.noOutput')}</p>
                            {call.error && <p className="danger-text">{call.error}</p>}
                          </details>
                        ))}
                      </details>
                    ))}
                  </div>
                </section>
              )
            )
          ) : (
            <section className="inspector-section">
              <div className="section-heading">
                <div>
                  <h2>{t('inspector.taskRecords')}</h2>
                  <p>{t('inspector.taskRecordsHint')}</p>
                </div>
              </div>
              <div className="task-list">
                {tasks.length === 0 && (
                  <div className="panel-empty">
                    <Clock3 size={20} aria-hidden="true" />
                    <p>{t('inspector.noTasks')}</p>
                  </div>
                )}
                {tasks.map((task) => {
                  const bot = room?.bots.find((item) => item.id === task.assignee_bot_id)
                  return (
                    <button
                      type="button"
                      className="task-row"
                      key={task.id}
                      onClick={() => onSelectTask(task.id)}
                    >
                      <div className="task-row-top">
                        <strong>{bot?.name ?? t('inspector.botFallback')}</strong>
                        <StatusBadge status={task.status} />
                      </div>
                      <p>{task.goal}</p>
                      <span className="task-row-time">
                        {new Date(task.created_at).toLocaleTimeString(locale, {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </button>
                  )
                })}
              </div>
            </section>
          )}
        </div>
      )}
    </aside>
  )
}
