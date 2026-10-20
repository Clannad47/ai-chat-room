import { useEffect, useState, type FormEvent } from 'react'
import { CheckCircle2, LoaderCircle, Save, X } from 'lucide-react'
import { api } from '../api'
import { useI18n } from '../i18n'
import type { LLMSettings } from '../types'

type Props = {
  onClose: () => void
}

export function ModelSettings({ onClose }: Props) {
  const { t } = useI18n()
  const [settings, setSettings] = useState<LLMSettings | null>(null)
  const [provider, setProvider] = useState('openai')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let active = true
    void api
      .getLLMSettings()
      .then((value) => {
        if (!active) return
        setSettings(value)
        setProvider(value.provider)
        setModel(value.model)
        setBaseUrl(value.base_url ?? '')
      })
      .catch((caught: unknown) => {
        if (active) setError(caught instanceof Error ? caught.message : t('settings.loadError'))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [t])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!model.trim() || saving) return
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      const updated = await api.updateLLMSettings({
        provider,
        model: model.trim(),
        base_url: baseUrl.trim() || null,
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        ...(clearKey ? { clear_api_key: true } : {}),
      })
      setSettings(updated)
      setModel(updated.model)
      setBaseUrl(updated.base_url ?? '')
      setApiKey('')
      setClearKey(false)
      setSaved(true)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : t('settings.saveError'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        className="settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-settings-title"
      >
        <header className="settings-header">
          <div>
            <span className="eyebrow">{t('settings.eyebrow')}</span>
            <h2 id="model-settings-title">{t('settings.title')}</h2>
            <p>{t('settings.subtitle')}</p>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label={t('settings.close')}
            title={t('sidebar.close')}
          >
            <X size={17} />
          </button>
        </header>

        <div className="settings-body">
          {loading ? (
            <div className="settings-loading" aria-live="polite">
              <LoaderCircle size={18} className="spin" aria-hidden="true" />
              <span>{t('settings.loading')}</span>
            </div>
          ) : (
            <form className="stack-form" onSubmit={submit}>
              <label>
                <span>{t('settings.provider')}</span>
                <select value={provider} onChange={(event) => setProvider(event.target.value)}>
                  <option value="openai">{t('settings.providerOption')}</option>
                </select>
                <small>{t('settings.providerHint')}</small>
              </label>
              <label>
                <span>{t('settings.defaultModel')}</span>
                <input
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder="deepseek-v4.1-flash"
                  maxLength={100}
                  autoFocus
                  required
                />
                <small>{t('settings.defaultModelHint')}</small>
              </label>
              <label>
                <span>{t('settings.baseUrl')}</span>
                <input
                  value={baseUrl}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  placeholder="https://api.openai.com/v1"
                  maxLength={500}
                />
                <small>{t('settings.baseUrlHint')}</small>
              </label>
              <label>
                <span>{t('settings.apiKey')}</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => {
                    setApiKey(event.target.value)
                    if (event.target.value) setClearKey(false)
                  }}
                  placeholder={
                    settings?.api_key_set
                      ? t('settings.apiKeySaved', {
                          hint: settings.api_key_hint ?? '••••',
                        })
                      : t('settings.apiKeyNotConfigured')
                  }
                  maxLength={500}
                  autoComplete="off"
                  spellCheck={false}
                />
                <small>{t('settings.apiKeyHint')}</small>
              </label>
              {settings?.api_key_set && (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={clearKey}
                    onChange={(event) => {
                      setClearKey(event.target.checked)
                      if (event.target.checked) setApiKey('')
                    }}
                  />
                  <span>{t('settings.removeKey')}</span>
                </label>
              )}

              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
              {saved && (
                <p className="settings-success" role="status">
                  <CheckCircle2 size={15} aria-hidden="true" />
                  {t('settings.saved')}
                </p>
              )}

              <div className="settings-actions">
                <button
                  type="submit"
                  className="button primary"
                  disabled={saving || !model.trim()}
                >
                  {saving ? (
                    <LoaderCircle size={16} className="spin" aria-hidden="true" />
                  ) : (
                    <Save size={16} aria-hidden="true" />
                  )}
                  {t('settings.save')}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
