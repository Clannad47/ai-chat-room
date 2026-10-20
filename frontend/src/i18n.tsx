import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { ConnectionState, TaskStatus } from './types'

const en = {
  'app.loadingWorkspace': 'Loading workspace…',
  'app.retry': 'Retry',
  'app.dismissError': 'Dismiss error',
  'app.closePanels': 'Close open panels',
  'app.loadWorkspaceError': 'Could not load the workspace',
  'app.loadRoomError': 'Could not load this room',
  'app.loadTaskError': 'Could not load task',
  'app.selectRoomFirst': 'Select a room first',

  'connection.connecting': 'Connecting',
  'connection.live': 'Live',
  'connection.reconnecting': 'Reconnecting',
  'connection.offline': 'Offline',

  'sidebar.subtitle': 'Human + agent workspace',
  'sidebar.rooms': 'Rooms',
  'sidebar.createRoom': 'Create room',
  'sidebar.closeNewRoomForm': 'Close new room form',
  'sidebar.close': 'Close',
  'sidebar.roomName': 'Room name',
  'sidebar.roomNamePlaceholder': 'Product launch',
  'sidebar.description': 'Description',
  'sidebar.descriptionPlaceholder': 'What is this room for?',
  'sidebar.botsInRoom': 'Bots in this room',
  'sidebar.createBotFirst': 'Create a bot from the details panel first.',
  'sidebar.noRooms': 'No rooms yet.',
  'sidebar.createFirstRoom': 'Create the first room',
  'sidebar.noDescription': 'No description',
  'sidebar.yourRooms': 'Your rooms',
  'sidebar.presetAccount': 'Preset account',
  'sidebar.connecting': 'Connecting…',
  'sidebar.modelSettings': 'Model settings',
  'sidebar.language': 'Language',
  'sidebar.createRoomError': 'Could not create room',

  'chat.ariaChat': 'Chat',
  'chat.openingRoom': 'Opening room…',
  'chat.noRoomSelected': 'No room selected',
  'chat.noRoomHint': 'Create a room to start chatting with humans and AI collaborators.',
  'chat.openRooms': 'Open rooms',
  'chat.chatIn': 'Chat in {name}',
  'chat.roomsTitle': 'Rooms',
  'chat.sharedRoom': 'Shared room for humans and bots',
  'chat.botCountSingular': 'bot',
  'chat.botCountPlural': 'bots',
  'chat.botCountTitle': '{count} bots in this room',
  'chat.openRoomDetails': 'Open room details',
  'chat.roomDetails': 'Room details',
  'chat.loadingMessages': 'Loading messages',
  'chat.startConversation': 'Start the conversation',
  'chat.startHintWithBots': 'Send a message and mention a bot with @ to put it to work.',
  'chat.startHintNoBots': 'Add a bot from the details panel, then mention it with @.',
  'chat.task': 'Task',
  'chat.taskTitle': 'Task {status}',
  'chat.workingOne': '{name} is working…',
  'chat.workingMany': '{count} bot tasks are queued or running…',
  'chat.aBot': 'A bot',

  'composer.mentionBot': 'Mention a bot',
  'composer.message': 'Message',
  'composer.placeholderMention': 'Message the room… use @ to mention a bot',
  'composer.placeholder': 'Message the room…',
  'composer.send': 'send',
  'composer.newline': 'newline',
  'composer.sendMessage': 'Send message',
  'composer.aiCollaborator': 'AI collaborator',
  'composer.sendError': 'Message failed to send',

  'inspector.sections': 'Room detail sections',
  'inspector.closeRoomDetails': 'Close room details',
  'inspector.agentsTab': 'Agents',
  'inspector.tasksTab': 'Tasks',
  'inspector.roomAgents': 'Room agents',
  'inspector.roomAgentsHint': 'Bots that can be mentioned in this room.',
  'inspector.closeBotForm': 'Close bot form',
  'inspector.createBot': 'Create bot',
  'inspector.name': 'Name',
  'inspector.namePlaceholder': 'Researcher',
  'inspector.nameHint': 'Letters, numbers, dashes, or CJK. No spaces.',
  'inspector.description': 'Description',
  'inspector.descriptionPlaceholder': 'Finds and verifies evidence',
  'inspector.persona': 'Persona',
  'inspector.personaPlaceholder': 'Careful, concise, cites what it used.',
  'inspector.modelOverride': 'Model override',
  'inspector.defaultModel': 'Default model',
  'inspector.tools': 'Tools',
  'inspector.noBots': 'No bots in this room yet.',
  'inspector.toolCount': '{count} tools',
  'inspector.removeBot': 'Remove {name} from this room',
  'inspector.removeFromRoom': 'Remove from room',
  'inspector.addExistingBot': 'Add an existing bot',
  'inspector.chooseBot': 'Choose a bot…',
  'inspector.add': 'Add',
  'inspector.allTasks': 'All tasks',
  'inspector.taskEyebrow': 'Task',
  'inspector.depth': 'Depth',
  'inspector.created': 'Created',
  'inspector.taskId': 'Task ID',
  'inspector.cancelTask': 'Cancel task',
  'inspector.runs': 'Runs',
  'inspector.noRun': 'No run has started yet.',
  'inspector.attempt': 'Attempt {count}',
  'inspector.inputTokens': '{count} input tokens',
  'inspector.outputTokens': '{count} output tokens',
  'inspector.noOutput': '(no output)',
  'inspector.taskRecords': 'Task records',
  'inspector.taskRecordsHint': 'Every mention creates a durable task.',
  'inspector.noTasks': 'No tasks yet. Mention a bot to start one.',
  'inspector.botFallback': 'Bot',
  'inspector.aiCollaborator': 'AI collaborator',
  'inspector.actionFailed': 'Action failed',

  'tools.getRoomHistory.label': 'Read room history',
  'tools.getRoomHistory.hint': 'Look up earlier messages',
  'tools.delegateToBot.label': 'Delegate to a bot',
  'tools.delegateToBot.hint': 'Ask a teammate and create a child task',
  'tools.fetchUrl.label': 'Fetch a public URL',
  'tools.fetchUrl.hint': 'Read text from an allowed public page',

  'settings.eyebrow': 'Model',
  'settings.title': 'Model configuration',
  'settings.subtitle': 'Changes apply to new tasks immediately. No restart required.',
  'settings.close': 'Close model settings',
  'settings.loading': 'Loading configuration…',
  'settings.provider': 'Provider',
  'settings.providerOption': 'OpenAI compatible',
  'settings.providerHint': 'Any service that implements the Chat Completions API.',
  'settings.defaultModel': 'Default model',
  'settings.defaultModelHint': 'Bots with a model override keep using their own model.',
  'settings.baseUrl': 'Base URL',
  'settings.baseUrlHint': 'Leave blank to use the provider default.',
  'settings.apiKey': 'API key',
  'settings.apiKeySaved': 'Saved ({hint}); leave blank to keep',
  'settings.apiKeyNotConfigured': 'Not configured',
  'settings.apiKeyHint': 'The key is stored on the server and never returned to the browser.',
  'settings.removeKey': 'Remove the stored API key',
  'settings.saved': 'Saved. New tasks use this configuration immediately.',
  'settings.save': 'Save settings',
  'settings.loadError': 'Could not load settings',
  'settings.saveError': 'Could not save settings',

  'status.queued': 'Queued',
  'status.running': 'Working',
  'status.succeeded': 'Done',
  'status.failed': 'Failed',
  'status.cancelled': 'Cancelled',
} as const

export type MessageKey = keyof typeof en
export type Language = 'zh' | 'en'

export const STATUS_MESSAGE_KEYS: Record<TaskStatus, MessageKey> = {
  queued: 'status.queued',
  running: 'status.running',
  succeeded: 'status.succeeded',
  failed: 'status.failed',
  cancelled: 'status.cancelled',
}

export const CONNECTION_MESSAGE_KEYS: Record<ConnectionState, MessageKey> = {
  connecting: 'connection.connecting',
  live: 'connection.live',
  reconnecting: 'connection.reconnecting',
  offline: 'connection.offline',
}

const zh: Record<MessageKey, string> = {
  'app.loadingWorkspace': '正在加载工作区…',
  'app.retry': '重试',
  'app.dismissError': '关闭错误提示',
  'app.closePanels': '关闭面板',
  'app.loadWorkspaceError': '无法加载工作区',
  'app.loadRoomError': '无法加载该房间',
  'app.loadTaskError': '无法加载任务',
  'app.selectRoomFirst': '请先选择一个房间',

  'connection.connecting': '连接中',
  'connection.live': '在线',
  'connection.reconnecting': '重连中',
  'connection.offline': '离线',

  'sidebar.subtitle': '人类 + Agent 工作空间',
  'sidebar.rooms': '房间',
  'sidebar.createRoom': '创建房间',
  'sidebar.closeNewRoomForm': '关闭新建房间表单',
  'sidebar.close': '关闭',
  'sidebar.roomName': '房间名称',
  'sidebar.roomNamePlaceholder': '产品发布',
  'sidebar.description': '描述',
  'sidebar.descriptionPlaceholder': '这个房间用来做什么？',
  'sidebar.botsInRoom': '房间中的 Bot',
  'sidebar.createBotFirst': '请先在详情面板中创建一个 Bot。',
  'sidebar.noRooms': '还没有房间。',
  'sidebar.createFirstRoom': '创建第一个房间',
  'sidebar.noDescription': '暂无描述',
  'sidebar.yourRooms': '你的房间',
  'sidebar.presetAccount': '预设账户',
  'sidebar.connecting': '连接中…',
  'sidebar.modelSettings': '模型设置',
  'sidebar.language': '语言',
  'sidebar.createRoomError': '无法创建房间',

  'chat.ariaChat': '聊天',
  'chat.openingRoom': '正在打开房间…',
  'chat.noRoomSelected': '未选择房间',
  'chat.noRoomHint': '创建房间，开始与人类和 AI 协作者聊天。',
  'chat.openRooms': '打开房间列表',
  'chat.chatIn': '在 {name} 中聊天',
  'chat.roomsTitle': '房间',
  'chat.sharedRoom': '人类与 Bot 共享的房间',
  'chat.botCountSingular': '个 Bot',
  'chat.botCountPlural': '个 Bot',
  'chat.botCountTitle': '该房间有 {count} 个 Bot',
  'chat.openRoomDetails': '打开房间详情',
  'chat.roomDetails': '房间详情',
  'chat.loadingMessages': '正在加载消息',
  'chat.startConversation': '开始对话',
  'chat.startHintWithBots': '发送消息并用 @ 提及 Bot，让它开始工作。',
  'chat.startHintNoBots': '从详情面板添加 Bot，然后用 @ 提及它。',
  'chat.task': '任务',
  'chat.taskTitle': '任务状态：{status}',
  'chat.workingOne': '{name} 正在工作…',
  'chat.workingMany': '{count} 个 Bot 任务正在排队或运行…',
  'chat.aBot': '某个 Bot',

  'composer.mentionBot': '提及 Bot',
  'composer.message': '消息',
  'composer.placeholderMention': '给房间发消息… 输入 @ 提及 Bot',
  'composer.placeholder': '给房间发消息…',
  'composer.send': '发送',
  'composer.newline': '换行',
  'composer.sendMessage': '发送消息',
  'composer.aiCollaborator': 'AI 协作者',
  'composer.sendError': '消息发送失败',

  'inspector.sections': '房间详情分区',
  'inspector.closeRoomDetails': '关闭房间详情',
  'inspector.agentsTab': '智能体',
  'inspector.tasksTab': '任务',
  'inspector.roomAgents': '房间智能体',
  'inspector.roomAgentsHint': '可在此房间中被提及的 Bot。',
  'inspector.closeBotForm': '关闭 Bot 表单',
  'inspector.createBot': '创建 Bot',
  'inspector.name': '名称',
  'inspector.namePlaceholder': '研究员',
  'inspector.nameHint': '字母、数字、短横线或中文，不能有空格。',
  'inspector.description': '描述',
  'inspector.descriptionPlaceholder': '查找并验证证据',
  'inspector.persona': '人设',
  'inspector.personaPlaceholder': '谨慎、简洁，并说明使用了哪些内容。',
  'inspector.modelOverride': '模型覆盖',
  'inspector.defaultModel': '默认模型',
  'inspector.tools': '工具',
  'inspector.noBots': '此房间还没有 Bot。',
  'inspector.toolCount': '{count} 个工具',
  'inspector.removeBot': '将 {name} 移出此房间',
  'inspector.removeFromRoom': '移出房间',
  'inspector.addExistingBot': '添加已有 Bot',
  'inspector.chooseBot': '选择 Bot…',
  'inspector.add': '添加',
  'inspector.allTasks': '全部任务',
  'inspector.taskEyebrow': '任务',
  'inspector.depth': '深度',
  'inspector.created': '创建时间',
  'inspector.taskId': '任务 ID',
  'inspector.cancelTask': '取消任务',
  'inspector.runs': '运行记录',
  'inspector.noRun': '尚未开始运行。',
  'inspector.attempt': '第 {count} 次尝试',
  'inspector.inputTokens': '输入 Token：{count}',
  'inspector.outputTokens': '输出 Token：{count}',
  'inspector.noOutput': '（无输出）',
  'inspector.taskRecords': '任务记录',
  'inspector.taskRecordsHint': '每次提及都会创建一个持久化任务。',
  'inspector.noTasks': '还没有任务。提及一个 Bot 来创建任务。',
  'inspector.botFallback': 'Bot',
  'inspector.aiCollaborator': 'AI 协作者',
  'inspector.actionFailed': '操作失败',

  'tools.getRoomHistory.label': '读取房间历史',
  'tools.getRoomHistory.hint': '查看更早的消息',
  'tools.delegateToBot.label': '委派给 Bot',
  'tools.delegateToBot.hint': '请求队友协助并创建子任务',
  'tools.fetchUrl.label': '抓取公网 URL',
  'tools.fetchUrl.hint': '读取允许的公开页面文本',

  'settings.eyebrow': '模型',
  'settings.title': '模型配置',
  'settings.subtitle': '修改将立即应用于新任务，无需重启。',
  'settings.close': '关闭模型设置',
  'settings.loading': '正在加载配置…',
  'settings.provider': '服务商',
  'settings.providerOption': 'OpenAI 兼容',
  'settings.providerHint': '任何实现 Chat Completions API 的服务。',
  'settings.defaultModel': '默认模型',
  'settings.defaultModelHint': '设置了模型覆盖的 Bot 仍使用自己的模型。',
  'settings.baseUrl': 'Base URL',
  'settings.baseUrlHint': '留空则使用服务商默认地址。',
  'settings.apiKey': 'API Key',
  'settings.apiKeySaved': '已保存（{hint}），留空保持不变',
  'settings.apiKeyNotConfigured': '未配置',
  'settings.apiKeyHint': '密钥只保存在服务端，不会返回浏览器。',
  'settings.removeKey': '移除已保存的 API Key',
  'settings.saved': '已保存，新任务将立即使用此配置。',
  'settings.save': '保存设置',
  'settings.loadError': '无法加载设置',
  'settings.saveError': '无法保存设置',

  'status.queued': '排队中',
  'status.running': '执行中',
  'status.succeeded': '已完成',
  'status.failed': '失败',
  'status.cancelled': '已取消',
}

const dictionaries: Record<Language, Record<MessageKey, string>> = { en, zh }
const STORAGE_KEY = 'ai-chat-room.language'

export const LANGUAGE_OPTIONS: { value: Language; label: string }[] = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
]

function readStoredLanguage(): Language {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored === 'en' || stored === 'zh' ? stored : 'zh'
  } catch {
    return 'zh'
  }
}

type I18nValue = {
  language: Language
  locale: string
  setLanguage: (language: Language) => void
  t: (key: MessageKey, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(readStoredLanguage)

  useEffect(() => {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'
    try {
      window.localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // Storage can be unavailable in private or restricted contexts.
    }
  }, [language])

  const t = useCallback(
    (key: MessageKey, params?: Record<string, string | number>) => {
      const template = dictionaries[language][key]
      if (!params) return template
      return template.replace(/\{(\w+)\}/g, (match, name: string) =>
        name in params ? String(params[name]) : match,
      )
    },
    [language],
  )

  const value = useMemo(
    () => ({
      language,
      locale: language === 'zh' ? 'zh-CN' : 'en-US',
      setLanguage,
      t,
    }),
    [language, t],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n must be used inside I18nProvider')
  return value
}
