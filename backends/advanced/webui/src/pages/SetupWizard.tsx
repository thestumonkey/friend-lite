import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Key,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  ExternalLink,
  Sparkles,
  X,
} from 'lucide-react'
import { wizardApi } from '../services/api'
import { getStorageKey } from '../utils/storage'

interface ApiKeysForm {
  openai_api_key: string
  deepgram_api_key: string
  mistral_api_key: string
}

interface Message {
  type: 'success' | 'error' | 'info'
  text: string
}

const API_KEY_LINKS = {
  openai: 'https://platform.openai.com/api-keys',
  deepgram: 'https://console.deepgram.com/signup',
  mistral: 'https://console.mistral.ai/api-keys/',
}

export default function SetupWizard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)

  // API Keys form state (core keys only)
  const [apiKeys, setApiKeys] = useState<ApiKeysForm>({
    openai_api_key: '',
    deepgram_api_key: '',
    mistral_api_key: '',
  })

  // API Keys visibility state
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({
    openai_api_key: false,
    deepgram_api_key: false,
    mistral_api_key: false,
  })

  useEffect(() => {
    loadWizardStatus()
  }, [])

  const loadWizardStatus = async () => {
    try {
      setLoading(true)
      const [statusResponse, keysResponse] = await Promise.all([
        wizardApi.getStatus(),
        wizardApi.getApiKeys()
      ])

      // If wizard already completed, redirect to main app
      if (statusResponse.data.wizard_completed) {
        navigate('/')
        return
      }

      // Load existing keys (will be masked if already configured)
      const keys = keysResponse.data
      setApiKeys({
        openai_api_key: keys.openai_api_key || '',
        deepgram_api_key: keys.deepgram_api_key || '',
        mistral_api_key: keys.mistral_api_key || '',
      })
    } catch (error: any) {
      console.error('Failed to load wizard status:', error)
      showMessage('error', 'Failed to load setup status')
    } finally {
      setLoading(false)
    }
  }

  const saveApiKeys = async () => {
    try {
      setSaving(true)

      // Only send non-empty keys (skip masked values)
      const keysToUpdate: any = {}
      Object.entries(apiKeys).forEach(([key, value]) => {
        if (value && !value.startsWith('***')) {
          keysToUpdate[key] = value
        }
      })

      if (Object.keys(keysToUpdate).length === 0) {
        showMessage('info', 'No API keys to save')
        return
      }

      await wizardApi.updateApiKeys(keysToUpdate)
      showMessage('success', 'API keys saved successfully! Redirecting...')

      // Clear wizard_dismissed flag since we've successfully completed setup
      localStorage.removeItem(getStorageKey('wizard_dismissed'))

      // Redirect to main app after short delay
      setTimeout(() => {
        navigate('/')
      }, 1500)
    } catch (error: any) {
      console.error('Failed to save API keys:', error)
      showMessage('error', error.response?.data?.detail || 'Failed to save API keys')
    } finally {
      setSaving(false)
    }
  }

  const skipWizard = () => {
    localStorage.setItem(getStorageKey('wizard_dismissed'), 'true')
    navigate('/')
  }

  const showMessage = (type: 'success' | 'error' | 'info', text: string) => {
    setMessage({ type, text })
    setTimeout(() => setMessage(null), 5000)
  }

  const toggleApiKeyVisibility = (field: string) => {
    setShowApiKeys(prev => ({ ...prev, [field]: !prev[field] }))
  }

  const updateApiKey = (field: keyof ApiKeysForm, value: string) => {
    setApiKeys(prev => ({ ...prev, [field]: value }))
  }

  const canSave = () => {
    // Require at least OpenAI and one transcription provider
    const hasOpenAI = apiKeys.openai_api_key && !apiKeys.openai_api_key.startsWith('***')
    const hasTranscription =
      (apiKeys.deepgram_api_key && !apiKeys.deepgram_api_key.startsWith('***')) ||
      (apiKeys.mistral_api_key && !apiKeys.mistral_api_key.startsWith('***'))
    return hasOpenAI && hasTranscription
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4">
      <div className="max-w-2xl w-full bg-white dark:bg-gray-800 rounded-lg shadow-xl">
        {/* Header */}
        <div className="p-8 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/20 rounded-lg flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  Welcome to Chronicle
                </h1>
                <p className="text-gray-600 dark:text-gray-400 mt-1">
                  Configure your API keys to get started
                </p>
              </div>
            </div>
            <button
              onClick={skipWizard}
              className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
              Skip
            </button>
          </div>
        </div>

        {/* Message Banner */}
        {message && (
          <div className={`p-4 mx-8 mt-4 rounded-lg flex items-center gap-2 ${
            message.type === 'success'
              ? 'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400'
              : message.type === 'error'
              ? 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-400'
              : 'bg-blue-100 dark:bg-blue-900/20 text-blue-800 dark:text-blue-400'
          }`}>
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{message.text}</span>
          </div>
        )}

        {/* Content */}
        <div className="p-8">
          <div className="space-y-6">
            {/* Info Banner */}
            <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
              <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-2">
                Quick Start Requirements
              </h3>
              <ul className="space-y-1 text-sm text-blue-800 dark:text-blue-300">
                <li>• <strong>OpenAI API Key</strong> - For memory extraction and chat</li>
                <li>• <strong>Deepgram or Mistral API Key</strong> - For audio transcription</li>
              </ul>
            </div>

            {/* API Key Fields */}
            <div className="space-y-4">
              {/* OpenAI */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    <Key className="w-4 h-4 inline mr-1" />
                    OpenAI API Key *
                  </label>
                  <a
                    href={API_KEY_LINKS.openai}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                  >
                    Get API Key <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showApiKeys.openai_api_key ? 'text' : 'password'}
                    value={apiKeys.openai_api_key}
                    onChange={(e) => updateApiKey('openai_api_key', e.target.value)}
                    placeholder="sk-..."
                    className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => toggleApiKeyVisibility('openai_api_key')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                  >
                    {showApiKeys.openai_api_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Required for memory extraction and chat features
                </p>
              </div>

              {/* Deepgram */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    <Key className="w-4 h-4 inline mr-1" />
                    Deepgram API Key *
                  </label>
                  <a
                    href={API_KEY_LINKS.deepgram}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                  >
                    Get API Key <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showApiKeys.deepgram_api_key ? 'text' : 'password'}
                    value={apiKeys.deepgram_api_key}
                    onChange={(e) => updateApiKey('deepgram_api_key', e.target.value)}
                    placeholder="Enter Deepgram API key"
                    className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => toggleApiKeyVisibility('deepgram_api_key')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                  >
                    {showApiKeys.deepgram_api_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  High-quality audio transcription (recommended)
                </p>
              </div>

              {/* Mistral (Optional) */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                    <Key className="w-4 h-4 inline mr-1" />
                    Mistral API Key (Optional)
                  </label>
                  <a
                    href={API_KEY_LINKS.mistral}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                  >
                    Get API Key <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showApiKeys.mistral_api_key ? 'text' : 'password'}
                    value={apiKeys.mistral_api_key}
                    onChange={(e) => updateApiKey('mistral_api_key', e.target.value)}
                    placeholder="Enter Mistral API key"
                    className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => toggleApiKeyVisibility('mistral_api_key')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                  >
                    {showApiKeys.mistral_api_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Alternative to Deepgram for transcription
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-8 border-t border-gray-200 dark:border-gray-700 flex justify-end gap-3">
          <button
            onClick={skipWizard}
            className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            Skip for now
          </button>
          <button
            onClick={saveApiKeys}
            disabled={!canSave() || saving}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Key className="w-5 h-5" />
                Save & Continue
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
