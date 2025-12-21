import { useState, useEffect } from 'react'
import { Server, Play, Square, RotateCw, RefreshCw, CheckCircle, XCircle, AlertCircle, FileText, Clock } from 'lucide-react'
import { servicesApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface ServiceInfo {
  name: string
  container_id: string | null
  status: string
  image: string | null
  created: string | null
  ports: Record<string, string>
  health: string | null
  error: string | null
  description: string
  required: boolean
  user_controllable: boolean
}

interface ServicesResponse {
  services: ServiceInfo[]
  docker_available: boolean
  status: string
}

export default function Services() {
  const { user } = useAuth()
  const [services, setServices] = useState<ServiceInfo[]>([])
  const [dockerAvailable, setDockerAvailable] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const [selectedService, setSelectedService] = useState<string | null>(null)
  const [logs, setLogs] = useState<string | null>(null)
  const [logsLoading, setLogsLoading] = useState(false)

  const fetchServices = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await servicesApi.getServices(true)
      const data: ServicesResponse = response.data
      setServices(data.services || [])
      setDockerAvailable(data.docker_available)
      setLastUpdated(new Date())
    } catch (err: any) {
      console.error('Error fetching services:', err)
      setError(err.response?.data?.error || err.message || 'Failed to fetch services')
      if (err.response?.status === 503) {
        setDockerAvailable(false)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchServices()
    const interval = setInterval(fetchServices, 10000) // Refresh every 10 seconds
    return () => clearInterval(interval)
  }, [])

  const handleServiceAction = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    setActionLoading(prev => ({ ...prev, [serviceName]: true }))
    setError(null)
    try {
      switch (action) {
        case 'start':
          await servicesApi.startService(serviceName)
          break
        case 'stop':
          await servicesApi.stopService(serviceName)
          break
        case 'restart':
          await servicesApi.restartService(serviceName)
          break
      }

      // Refresh services list after action
      setTimeout(fetchServices, 1000)
    } catch (err: any) {
      console.error(`Error ${action}ing service ${serviceName}:`, err)
      setError(err.response?.data?.error || err.message || `Failed to ${action} service`)
    } finally {
      setActionLoading(prev => ({ ...prev, [serviceName]: false }))
    }
  }

  const handleViewLogs = async (serviceName: string) => {
    setSelectedService(serviceName)
    setLogsLoading(true)
    setLogs(null)
    try {
      const response = await servicesApi.getLogs(serviceName, 200)
      setLogs(response.data.logs || 'No logs available')
    } catch (err: any) {
      console.error(`Error fetching logs for ${serviceName}:`, err)
      setLogs(`Error fetching logs: ${err.response?.data?.error || err.message}`)
    } finally {
      setLogsLoading(false)
    }
  }

  const getStatusIcon = (status: string, health?: string | null) => {
    if (status === 'running') {
      if (health === 'healthy') {
        return <CheckCircle className="w-5 h-5 text-green-500" />
      } else if (health === 'unhealthy') {
        return <AlertCircle className="w-5 h-5 text-red-500" />
      } else if (health === 'starting') {
        return <Clock className="w-5 h-5 text-yellow-500" />
      }
      return <CheckCircle className="w-5 h-5 text-green-500" />
    } else if (status === 'exited' || status === 'stopped') {
      return <Square className="w-5 h-5 text-gray-500" />
    } else if (status === 'not_found') {
      return <XCircle className="w-5 h-5 text-gray-400" />
    }
    return <AlertCircle className="w-5 h-5 text-yellow-500" />
  }

  const getStatusColor = (status: string) => {
    if (status === 'running') return 'text-green-600 bg-green-50'
    if (status === 'exited' || status === 'stopped') return 'text-gray-600 bg-gray-50'
    if (status === 'not_found') return 'text-gray-400 bg-gray-50'
    return 'text-yellow-600 bg-yellow-50'
  }

  if (!user?.is_superuser) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">Access denied. Services management requires admin privileges.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Server className="w-8 h-8 text-blue-600" />
            Docker Services
          </h1>
          <p className="text-gray-600 mt-2">
            Manage Docker containers for Chronicle infrastructure
          </p>
        </div>
        <button
          onClick={fetchServices}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {!dockerAvailable && (
        <div className="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <p className="text-yellow-800">Docker is not available. Make sure Docker daemon is running.</p>
        </div>
      )}

      {lastUpdated && (
        <div className="mb-4 text-sm text-gray-500">
          Last updated: {lastUpdated.toLocaleTimeString()}
        </div>
      )}

      <div className="grid gap-6">
        {services.map(service => (
          <div key={service.name} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-start gap-4 flex-1">
                {getStatusIcon(service.status, service.health)}
                <div className="flex-1">
                  <h3 className="text-xl font-semibold text-gray-900">{service.name}</h3>
                  <p className="text-gray-600 mt-1">{service.description}</p>
                  {service.container_id && (
                    <p className="text-sm text-gray-500 mt-1">Container ID: {service.container_id}</p>
                  )}
                  {service.image && (
                    <p className="text-sm text-gray-500">Image: {service.image}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(service.status)}`}>
                  {service.status}
                </span>
                {service.health && (
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    service.health === 'healthy' ? 'text-green-600 bg-green-50' :
                    service.health === 'unhealthy' ? 'text-red-600 bg-red-50' :
                    'text-yellow-600 bg-yellow-50'
                  }`}>
                    {service.health}
                  </span>
                )}
              </div>
            </div>

            {Object.keys(service.ports).length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Ports:</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(service.ports).map(([containerPort, hostPort]) => (
                    <span key={containerPort} className="px-2 py-1 bg-gray-100 rounded text-sm text-gray-700">
                      {hostPort} → {containerPort}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {service.error && (
              <div className="mb-4 bg-red-50 border border-red-200 rounded p-3">
                <p className="text-sm text-red-800">{service.error}</p>
              </div>
            )}

            <div className="flex items-center gap-3">
              {service.user_controllable && service.status !== 'running' && (
                <button
                  onClick={() => handleServiceAction(service.name, 'start')}
                  disabled={actionLoading[service.name]}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Play className="w-4 h-4" />
                  Start
                </button>
              )}
              {service.user_controllable && service.status === 'running' && !service.required && (
                <button
                  onClick={() => handleServiceAction(service.name, 'stop')}
                  disabled={actionLoading[service.name]}
                  className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Square className="w-4 h-4" />
                  Stop
                </button>
              )}
              {service.user_controllable && service.status === 'running' && (
                <button
                  onClick={() => handleServiceAction(service.name, 'restart')}
                  disabled={actionLoading[service.name]}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <RotateCw className="w-4 h-4" />
                  Restart
                </button>
              )}
              {service.status !== 'not_found' && (
                <button
                  onClick={() => handleViewLogs(service.name)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                >
                  <FileText className="w-4 h-4" />
                  View Logs
                </button>
              )}
              {service.required && (
                <span className="ml-auto text-sm text-gray-500 italic">Required service</span>
              )}
              {!service.user_controllable && (
                <span className="ml-auto text-sm text-gray-500 italic">System managed</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {services.length === 0 && !loading && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Server className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No services found</p>
        </div>
      )}

      {selectedService && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-6 border-b">
              <h2 className="text-2xl font-bold text-gray-900">Logs: {selectedService}</h2>
              <button
                onClick={() => setSelectedService(null)}
                className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              {logsLoading ? (
                <div className="text-center py-8">
                  <RefreshCw className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
                  <p className="text-gray-600">Loading logs...</p>
                </div>
              ) : (
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-xs overflow-x-auto whitespace-pre-wrap break-words">
                  {logs}
                </pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
