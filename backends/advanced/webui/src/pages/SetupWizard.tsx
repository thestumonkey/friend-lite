import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircle,
  ArrowRight,
  ArrowLeft,
  Key,
  Save,
  Eye,
  EyeOff,
  AlertCircle,
  Loader2,
  Download,
  ExternalLink,
  Sparkles,
  Settings,
  Sliders,
  X,
} from 'lucide-react'
import { wizardApi } from '../services/api'
import { getStorageKey } from '../utils/storage'

type WizardStep = 'setup_type' | 'api_keys' | 'complete'
type SetupType = 'basic' | 'intermediate' | 'customized'

interface ApiKeysForm {
  openai_api_key: string
  deepgram_api_key: string
  mistral_api_key: string
  hf_token: string
  langfuse_public_key: string
  langfuse_secret_key: string
  ngrok_authtoken: string
}

interface Message {
  type: 'success' | 'error' | 'info'
  text: string
}

const API_KEY_LINKS = {
  openai: 'https://platform.openai.com/api-keys',
  deepgram: 'https://console.deepgram.com/signup',
  mistral: 'https://console.mistral.ai/api-keys/',
  huggingface: 'https://huggingface.co/settings/tokens',
  langfuse: 'https://cloud.langfuse.com/',
  ngrok: 'https://dashboard.ngrok.com/get-started/your-authtoken',
}

export default function SetupWizard() {
  const navigate = useNavigate()
  const [currentStep, setCurrentStep] = useState<WizardStep>('setup_type')
  const [setupType, setSetupType] = useState<SetupType>('basic')
  const [completedSteps, setCompletedSteps] = useState<WizardStep[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message | null>(null)
  const [hasEnvKeys, setHasEnvKeys] = useState(false)

  // API Keys form state
  const [apiKeys, setApiKeys] = useState<ApiKeysForm>({
    openai_api_key: '',
    deepgram_api_key: '',
    mistral_api_key: '',
    hf_token: '',
    langfuse_public_key: '',
    langfuse_secret_key: '',
    ngrok_authtoken: '',
  })

  // API Keys visibility state
  const [showApiKeys, setShowApiKeys] = useState<Record<string, boolean>>({
    openai_api_key: false,
    deepgram_api_key: false,
    mistral_api_key: false,
    hf_token: false,
    langfuse_public_key: false,
    langfuse_secret_key: false,
    ngrok_authtoken: false,
  })

  useEffect(() => {
    loadWizardStatus()
  }, [])

  const loadWizardStatus = async () => {
    try {
      setLoading(true)
      const response = await wizardApi.getStatus()
      const status = response.data

      if (status.wizard_completed) {
        // Wizard already completed, redirect to main app
        navigate('/')
        return
      }

      setCurrentStep(status.current_step as WizardStep)
      setCompletedSteps(status.completed_steps as WizardStep[])
    } catch (error: any) {
      console.error('Failed to load wizard status:', error)
      showMessage('error', 'Failed to load setup status')
    } finally {
      setLoading(false)
    }
  }

  const detectEnvKeys = async () => {
    try {
      const response = await wizardApi.detectEnvKeys()
      const keys = response.data

      // Check if any keys were found
      const foundKeys = Object.values(keys).some(val => val !== null && val !== '')
      setHasEnvKeys(foundKeys)

      if (foundKeys) {
        showMessage('info', 'Found existing API keys in .env files. You can import them below.')
      }
    } catch (error: any) {
      console.error('Failed to detect env keys:', error)
    }
  }

  const importEnvKeys = async () => {
    try {
      setSaving(true)
      const response = await wizardApi.importEnvKeys()
      const keys = response.data

      // Update form with imported keys
      setApiKeys({
        openai_api_key: keys.openai_api_key || '',
        deepgram_api_key: keys.deepgram_api_key || '',
        mistral_api_key: keys.mistral_api_key || '',
        hf_token: keys.hf_token || '',
        langfuse_public_key: keys.langfuse_public_key || '',
        langfuse_secret_key: keys.langfuse_secret_key || '',
        ngrok_authtoken: keys.ngrok_authtoken || '',
      })

      showMessage('success', 'API keys imported successfully from .env files')
      setHasEnvKeys(false)
    } catch (error: any) {
      console.error('Failed to import env keys:', error)
      showMessage('error', error.response?.data?.detail || 'Failed to import API keys')
    } finally {
      setSaving(false)
    }
  }

  const loadApiKeys = async () => {
    try {
      const response = await wizardApi.getApiKeys()
      const keys = response.data

      // Update form with masked keys (to show which are configured)
      setApiKeys({
        openai_api_key: keys.openai_api_key || '',
        deepgram_api_key: keys.deepgram_api_key || '',
        mistral_api_key: keys.mistral_api_key || '',
        hf_token: keys.hf_token || '',
        langfuse_public_key: keys.langfuse_public_key || '',
        langfuse_secret_key: keys.langfuse_secret_key || '',
        ngrok_authtoken: keys.ngrok_authtoken || '',
      })

      // Also detect if there are keys in .env files
      await detectEnvKeys()
    } catch (error: any) {
      console.error('Failed to load API keys:', error)
      showMessage('error', 'Failed to load API keys')
    }
  }

  const saveApiKeys = async () => {
    try {
      setSaving(true)

      // Only send non-empty keys
      const keysToUpdate: any = {}
      Object.entries(apiKeys).forEach(([key, value]) => {
        if (value && !value.startsWith('***')) {
          keysToUpdate[key] = value
        }
      })

      await wizardApi.updateApiKeys(keysToUpdate)
      showMessage('success', 'API keys saved successfully')

      // Mark API keys step as complete
      if (!completedSteps.includes('api_keys')) {
        setCompletedSteps([...completedSteps, 'api_keys'])
      }

      return true
    } catch (error: any) {
      console.error('Failed to save API keys:', error)
      showMessage('error', error.response?.data?.detail || 'Failed to save API keys')
      return false
    } finally {
      setSaving(false)
    }
  }

  const completeWizard = async () => {
    try {
      setSaving(true)
      await wizardApi.complete()

      // Mark wizard as dismissed so it won't auto-redirect again
      localStorage.setItem(getStorageKey('wizard_dismissed'), 'true')

      showMessage('success', 'Setup complete! Redirecting...')

      // Redirect to main app after short delay
      setTimeout(() => {
        navigate('/')
      }, 1500)
    } catch (error: any) {
      console.error('Failed to complete wizard:', error)
      showMessage('error', 'Failed to complete setup')
    } finally {
      setSaving(false)
    }
  }

  const skipWizard = () => {
    // Mark wizard as dismissed
    localStorage.setItem(getStorageKey('wizard_dismissed'), 'true')

    // Redirect to main app
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

  const handleNext = async () => {
    if (currentStep === 'setup_type') {
      setCurrentStep('api_keys')
      await loadApiKeys()
    } else if (currentStep === 'api_keys') {
      const saved = await saveApiKeys()
      if (saved) {
        setCurrentStep('complete')
      }
    } else if (currentStep === 'complete') {
      await completeWizard()
    }
  }

  const handleBack = () => {
    if (currentStep === 'api_keys') {
      setCurrentStep('setup_type')
    } else if (currentStep === 'complete') {
      setCurrentStep('api_keys')
    }
  }

  const canProceed = () => {
    if (currentStep === 'setup_type') return true
    if (currentStep === 'api_keys') {
      if (setupType === 'basic') {
        // Basic: Require OpenAI and Deepgram
        const hasOpenAI = apiKeys.openai_api_key && !apiKeys.openai_api_key.startsWith('***')
        const hasDeepgram = apiKeys.deepgram_api_key && !apiKeys.deepgram_api_key.startsWith('***')
        return hasOpenAI && hasDeepgram
      } else if (setupType === 'intermediate') {
        // Intermediate: Require LLM and transcription (any providers)
        const hasLLM = apiKeys.openai_api_key && !apiKeys.openai_api_key.startsWith('***')
        const hasTranscription =
          (apiKeys.deepgram_api_key && !apiKeys.deepgram_api_key.startsWith('***')) ||
          (apiKeys.mistral_api_key && !apiKeys.mistral_api_key.startsWith('***'))
        return hasLLM && hasTranscription
      } else {
        // Customized: Require at least LLM OR transcription
        const hasLLM = apiKeys.openai_api_key && !apiKeys.openai_api_key.startsWith('***')
        const hasTranscription =
          (apiKeys.deepgram_api_key && !apiKeys.deepgram_api_key.startsWith('***')) ||
          (apiKeys.mistral_api_key && !apiKeys.mistral_api_key.startsWith('***'))
        return hasLLM || hasTranscription
      }
    }
    if (currentStep === 'complete') return true
    return false
  }

  const getVisibleApiKeyFields = () => {
    if (setupType === 'basic') {
      return ['openai_api_key', 'deepgram_api_key']
    } else if (setupType === 'intermediate') {
      return ['openai_api_key', 'deepgram_api_key', 'mistral_api_key']
    } else {
      return ['openai_api_key', 'deepgram_api_key', 'mistral_api_key', 'hf_token', 'langfuse_public_key', 'langfuse_secret_key', 'ngrok_authtoken']
    }
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
      <div className="max-w-4xl w-full bg-white dark:bg-gray-800 rounded-lg shadow-xl">
        {/* Header */}
        <div className="p-8 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
                Welcome to Chronicle
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                Let's get your system set up in just a few steps
              </p>
            </div>
            {/* Skip button (only show on setup_type and api_keys steps) */}
            {currentStep !== 'complete' && (
              <button
                onClick={skipWizard}
                className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="w-4 h-4" />
                Skip for now
              </button>
            )}
          </div>
        </div>

        {/* Progress Steps */}
        <div className="p-8 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            {/* Setup Type Step */}
            <div className="flex items-center flex-1">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                completedSteps.includes('setup_type') || currentStep !== 'setup_type'
                  ? 'bg-green-600'
                  : currentStep === 'setup_type'
                  ? 'bg-blue-600'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}>
                {completedSteps.includes('setup_type') || currentStep !== 'setup_type' ? (
                  <CheckCircle className="w-6 h-6 text-white" />
                ) : (
                  <Sliders className="w-6 h-6 text-white" />
                )}
              </div>
              <span className="ml-3 text-sm font-medium text-gray-900 dark:text-white hidden sm:inline">
                Setup Type
              </span>
            </div>

            {/* Connector */}
            <div className={`flex-1 h-1 mx-2 ${
              completedSteps.includes('setup_type') || currentStep === 'api_keys' || currentStep === 'complete'
                ? 'bg-green-600'
                : 'bg-gray-300 dark:bg-gray-600'
            }`} />

            {/* API Keys Step */}
            <div className="flex items-center flex-1">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                completedSteps.includes('api_keys') || currentStep === 'complete'
                  ? 'bg-green-600'
                  : currentStep === 'api_keys'
                  ? 'bg-blue-600'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}>
                {completedSteps.includes('api_keys') || currentStep === 'complete' ? (
                  <CheckCircle className="w-6 h-6 text-white" />
                ) : (
                  <Key className="w-6 h-6 text-white" />
                )}
              </div>
              <span className="ml-3 text-sm font-medium text-gray-900 dark:text-white hidden sm:inline">
                API Keys
              </span>
            </div>

            {/* Connector */}
            <div className={`flex-1 h-1 mx-2 ${
              currentStep === 'complete'
                ? 'bg-green-600'
                : 'bg-gray-300 dark:bg-gray-600'
            }`} />

            {/* Complete Step */}
            <div className="flex items-center flex-1">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                currentStep === 'complete'
                  ? 'bg-green-600'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}>
                <CheckCircle className="w-6 h-6 text-white" />
              </div>
              <span className="ml-3 text-sm font-medium text-gray-900 dark:text-white hidden sm:inline">
                Complete
              </span>
            </div>
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

        {/* Step Content */}
        <div className="p-8 min-h-[400px]">
          {/* Setup Type Step */}
          {currentStep === 'setup_type' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-2">
                  Welcome to Chronicle
                </h2>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                  Chronicle is your AI-powered personal memory system. Choose your setup type to get started.
                </p>
              </div>

              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  What you'll need:
                </h3>
                <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span><strong>OpenAI API Key</strong> - For memory extraction and LLM features</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span><strong>Deepgram or Mistral API Key</strong> - For audio transcription</span>
                  </li>
                </ul>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Basic Setup */}
                <button
                  onClick={() => setSetupType('basic')}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    setupType === 'basic'
                      ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Sparkles className={`w-6 h-6 ${setupType === 'basic' ? 'text-blue-600' : 'text-gray-500'}`} />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Basic
                    </h3>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    Quick setup with recommended providers
                  </p>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• OpenAI</li>
                    <li>• Deepgram</li>
                  </ul>
                </button>

                {/* Intermediate Setup */}
                <button
                  onClick={() => setSetupType('intermediate')}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    setupType === 'intermediate'
                      ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Settings className={`w-6 h-6 ${setupType === 'intermediate' ? 'text-blue-600' : 'text-gray-500'}`} />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Intermediate
                    </h3>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    Choose your LLM and transcription providers
                  </p>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• OpenAI</li>
                    <li>• Deepgram / Mistral</li>
                  </ul>
                </button>

                {/* Customized Setup */}
                <button
                  onClick={() => setSetupType('customized')}
                  className={`p-6 rounded-lg border-2 transition-all text-left ${
                    setupType === 'customized'
                      ? 'border-blue-600 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-300 dark:border-gray-600 hover:border-blue-400'
                  }`}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <Sliders className={`w-6 h-6 ${setupType === 'customized' ? 'text-blue-600' : 'text-gray-500'}`} />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                      Customized
                    </h3>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    Full control over all services
                  </p>
                  <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                    <li>• All LLM options</li>
                    <li>• All transcription options</li>
                    <li>• Optional services</li>
                  </ul>
                </button>
              </div>
            </div>
          )}

          {/* API Keys Step */}
          {currentStep === 'api_keys' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-2">
                  Configure API Keys
                </h2>
                <p className="text-gray-600 dark:text-gray-400">
                  {setupType === 'basic' && 'Enter your OpenAI and Deepgram API keys.'}
                  {setupType === 'intermediate' && 'Configure your LLM and transcription providers.'}
                  {setupType === 'customized' && 'Configure all your API keys and services.'}
                </p>
              </div>

              {/* Import from .env banner */}
              {hasEnvKeys && (
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <Download className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <div>
                        <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-1">
                          Existing API Keys Found
                        </h3>
                        <p className="text-sm text-blue-800 dark:text-blue-300">
                          We found API keys in your environment. Click below to import them to config.yaml.
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={importEnvKeys}
                      disabled={saving}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 text-sm font-medium whitespace-nowrap flex items-center gap-2"
                    >
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                      Import Keys
                    </button>
                  </div>
                </div>
              )}

              <div className="space-y-4">
                {/* Required Keys Section */}
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
                    Required Keys
                  </h3>

                  {getVisibleApiKeyFields().includes('openai_api_key') && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
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
                        Used for memory extraction and chat features
                      </p>
                    </div>
                  )}

                  {getVisibleApiKeyFields().includes('deepgram_api_key') && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          Deepgram API Key {setupType === 'basic' && '*'}
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
                  )}

                  {getVisibleApiKeyFields().includes('mistral_api_key') && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          Mistral API Key (Alternative)
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
                        Can be used instead of Deepgram for transcription
                      </p>
                    </div>
                  )}
                </div>

                {/* Optional Keys Section (only for customized) */}
                {setupType === 'customized' && (
                  <div className="space-y-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
                      Optional Keys
                    </h3>

                    {getVisibleApiKeyFields().includes('hf_token') && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            HuggingFace Token
                          </label>
                          <a
                            href={API_KEY_LINKS.huggingface}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                          >
                            Get Token <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="relative">
                          <input
                            type={showApiKeys.hf_token ? 'text' : 'password'}
                            value={apiKeys.hf_token}
                            onChange={(e) => updateApiKey('hf_token', e.target.value)}
                            placeholder="hf_..."
                            className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleApiKeyVisibility('hf_token')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                          >
                            {showApiKeys.hf_token ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                          </button>
                        </div>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                          For HuggingFace model access
                        </p>
                      </div>
                    )}

                    {getVisibleApiKeyFields().includes('langfuse_public_key') && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Langfuse Public Key
                          </label>
                          <a
                            href={API_KEY_LINKS.langfuse}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                          >
                            Get API Key <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="relative">
                          <input
                            type={showApiKeys.langfuse_public_key ? 'text' : 'password'}
                            value={apiKeys.langfuse_public_key}
                            onChange={(e) => updateApiKey('langfuse_public_key', e.target.value)}
                            placeholder="pk-lf-..."
                            className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleApiKeyVisibility('langfuse_public_key')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                          >
                            {showApiKeys.langfuse_public_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                          </button>
                        </div>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                          LLM observability and tracing
                        </p>
                      </div>
                    )}

                    {getVisibleApiKeyFields().includes('langfuse_secret_key') && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Langfuse Secret Key
                          </label>
                        </div>
                        <div className="relative">
                          <input
                            type={showApiKeys.langfuse_secret_key ? 'text' : 'password'}
                            value={apiKeys.langfuse_secret_key}
                            onChange={(e) => updateApiKey('langfuse_secret_key', e.target.value)}
                            placeholder="sk-lf-..."
                            className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleApiKeyVisibility('langfuse_secret_key')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                          >
                            {showApiKeys.langfuse_secret_key ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                          </button>
                        </div>
                      </div>
                    )}

                    {getVisibleApiKeyFields().includes('ngrok_authtoken') && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Ngrok Auth Token
                          </label>
                          <a
                            href={API_KEY_LINKS.ngrok}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400 flex items-center gap-1"
                          >
                            Get Token <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="relative">
                          <input
                            type={showApiKeys.ngrok_authtoken ? 'text' : 'password'}
                            value={apiKeys.ngrok_authtoken}
                            onChange={(e) => updateApiKey('ngrok_authtoken', e.target.value)}
                            placeholder="Enter Ngrok auth token"
                            className="w-full px-4 py-2 pr-12 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => toggleApiKeyVisibility('ngrok_authtoken')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                          >
                            {showApiKeys.ngrok_authtoken ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                          </button>
                        </div>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                          For exposing local services via tunnels
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Complete Step */}
          {currentStep === 'complete' && (
            <div className="space-y-6 text-center">
              <div className="flex justify-center">
                <div className="w-20 h-20 bg-green-100 dark:bg-green-900/20 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-12 h-12 text-green-600" />
                </div>
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-2">
                  Setup Complete!
                </h2>
                <p className="text-gray-600 dark:text-gray-400 text-lg">
                  Your Chronicle system is now configured and ready to use.
                </p>
              </div>
              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-left">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  Next Steps:
                </h3>
                <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span>Start recording conversations or upload audio files</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span>View and search your memories</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <span>Chat with your AI assistant about your memories</span>
                  </li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="p-8 border-t border-gray-200 dark:border-gray-700 flex justify-between">
          <button
            onClick={handleBack}
            disabled={currentStep === 'setup_type' || saving}
            className="px-6 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            Back
          </button>

          <button
            onClick={handleNext}
            disabled={!canProceed() || saving}
            className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                {currentStep === 'api_keys' ? 'Saving...' : 'Completing...'}
              </>
            ) : (
              <>
                {currentStep === 'complete' ? 'Go to Dashboard' : 'Next'}
                {currentStep === 'api_keys' && <Save className="w-5 h-5" />}
                {(currentStep === 'setup_type' || currentStep === 'complete') && <ArrowRight className="w-5 h-5" />}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
