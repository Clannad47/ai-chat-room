import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AtSign, LoaderCircle, SendHorizontal } from 'lucide-react'
import { useI18n } from '../i18n'
import type { Bot } from '../types'
import { Avatar } from './Avatar'

type Props = {
  bots: Bot[]
  disabled?: boolean
  onSend: (content: string) => Promise<void>
}

export function Composer({ bots, disabled, onSend }: Props) {
  const { t } = useI18n()
  const [content, setContent] = useState('')
  const [caret, setCaret] = useState(0)
  const [highlight, setHighlight] = useState(0)
  const [mentionDismissed, setMentionDismissed] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const beforeCaret = content.slice(0, caret)
  const mentionMatch = /(?:^|\s)@([^\s@]*)$/.exec(beforeCaret)
  const query = mentionMatch && !mentionDismissed ? mentionMatch[1] : null
  const suggestions =
    query === null
      ? []
      : bots
          .filter((bot) => bot.name.toLowerCase().includes(query.toLowerCase()))
          .slice(0, 6)
  const mentionStart = query === null ? null : caret - query.length - 1

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 152)}px`
  }, [content])

  const selectBot = (bot: Bot) => {
    if (mentionStart === null) return
    const next = `${content.slice(0, mentionStart)}@${bot.name} ${content.slice(caret)}`
    const nextCaret = mentionStart + bot.name.length + 2
    setMentionDismissed(false)
    setContent(next)
    setCaret(nextCaret)
    requestAnimationFrame(() => {
      textareaRef.current?.focus()
      textareaRef.current?.setSelectionRange(nextCaret, nextCaret)
    })
  }

  const send = async () => {
    const trimmed = content.trim()
    if (!trimmed || sending || disabled) return
    setSending(true)
    setError('')
    try {
      await onSend(trimmed)
      setContent('')
      setCaret(0)
      requestAnimationFrame(() => textareaRef.current?.focus())
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('composer.sendError'))
    } finally {
      setSending(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void send()
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return
    if (suggestions.length > 0) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setHighlight((current) => (current + 1) % suggestions.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setHighlight((current) => (current - 1 + suggestions.length) % suggestions.length)
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        selectBot(suggestions[highlight])
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        setMentionDismissed(true)
        return
      }
    }
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-field">
        {suggestions.length > 0 && (
          <div
            className="mention-popover"
            role="listbox"
            aria-label={t('composer.mentionBot')}
          >
            <div className="mention-heading">
              <AtSign size={13} aria-hidden="true" />
              {t('composer.mentionBot')}
            </div>
            {suggestions.map((bot, index) => (
              <button
                type="button"
                key={bot.id}
                role="option"
                aria-selected={index === highlight}
                className={`mention-option ${index === highlight ? 'highlight' : ''}`}
                onMouseDown={(event) => {
                  event.preventDefault()
                  selectBot(bot)
                }}
              >
                <Avatar name={bot.name} kind="bot" size="sm" />
                <span>
                  <strong>{bot.name}</strong>
                  <span>{bot.description || t('composer.aiCollaborator')}</span>
                </span>
              </button>
            ))}
          </div>
        )}
        <label className="sr-only" htmlFor="composer-input">
          {t('composer.message')}
        </label>
        <textarea
          id="composer-input"
          ref={textareaRef}
          value={content}
          rows={1}
          placeholder={
            bots.length > 0
              ? t('composer.placeholderMention')
              : t('composer.placeholder')
          }
          onChange={(event) => {
            setContent(event.target.value)
            setCaret(event.target.selectionStart)
            setMentionDismissed(false)
            setHighlight(0)
          }}
          onSelect={(event) => setCaret(event.currentTarget.selectionStart)}
          onKeyDown={onKeyDown}
          disabled={disabled}
        />
        <div className="composer-meta">
          <span>
            <kbd>Enter</kbd> {t('composer.send')} · <kbd>Shift</kbd> + <kbd>Enter</kbd>{' '}
            {t('composer.newline')}
          </span>
          <button
            type="submit"
            className="send-button"
            disabled={sending || disabled || !content.trim()}
            aria-label={t('composer.sendMessage')}
            title={t('composer.sendMessage')}
          >
            {sending ? (
              <LoaderCircle size={18} className="spin" aria-hidden="true" />
            ) : (
              <SendHorizontal size={18} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
