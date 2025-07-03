import { useState, useEffect } from 'react'

const EmailSearch = () => {
  const [email, setEmail] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken'))
  const [userInfo, setUserInfo] = useState(null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState('login') // 'login' or 'register'
  const [apiKey, setApiKey] = useState(localStorage.getItem('apiKey'))
  const [showStats, setShowStats] = useState(false)
  const [stats, setStats] = useState(null)

  // Проверка аутентификации при загрузке
  useEffect(() => {
    if (authToken) {
      verifyToken()
    } else if (apiKey) {
      verifyApiKey()
    }
  }, [authToken, apiKey])

  const verifyToken = async () => {
    try {
      const response = await fetch('/api/auth/verify-token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token: authToken })
      })
      
      if (response.ok) {
        const data = await response.json()
        setIsAuthenticated(true)
        setUserInfo(data.user)
      } else {
        localStorage.removeItem('authToken')
        setAuthToken(null)
      }
    } catch (error) {
      console.error('Ошибка проверки токена:', error)
    }
  }

  const verifyApiKey = async () => {
    try {
      const response = await fetch('/api/auth/verify-api-key', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ api_key: apiKey })
      })
      
      if (response.ok) {
        const data = await response.json()
        setIsAuthenticated(true)
        setUserInfo(data.user)
      } else {
        localStorage.removeItem('apiKey')
        setApiKey(null)
      }
    } catch (error) {
      console.error('Ошибка проверки API ключа:', error)
    }
  }

  const handleAuth = async (formData) => {
    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register'
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      })
      
      const data = await response.json()
      
      if (response.ok) {
        if (authMode === 'login') {
          const token = data.tokens.access_token
          localStorage.setItem('authToken', token)
          setAuthToken(token)
          setIsAuthenticated(true)
          setUserInfo(data.user)
        } else {
          // При регистрации показываем API ключ
          alert(`Регистрация успешна! Ваш API ключ: ${data.user.api_key}\nСохраните его в безопасном месте.`)
          localStorage.setItem('apiKey', data.user.api_key)
          setApiKey(data.user.api_key)
          setIsAuthenticated(true)
          setUserInfo(data.user)
        }
        setShowAuthModal(false)
        setError('')
      } else {
        setError(data.error || 'Ошибка аутентификации')
      }
    } catch (error) {
      setError('Ошибка соединения с сервером')
    }
  }

  const logout = () => {
    localStorage.removeItem('authToken')
    localStorage.removeItem('apiKey')
    setAuthToken(null)
    setApiKey(null)
    setIsAuthenticated(false)
    setUserInfo(null)
  }

  const searchEmail = async () => {
    if (!email.trim()) {
      setError('Пожалуйста, введите email адрес')
      return
    }

    setLoading(true)
    setError('')
    setResults(null)

    try {
      const headers = {
        'Content-Type': 'application/json',
      }

      // Добавляем аутентификацию если доступна
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      } else if (apiKey) {
        headers['X-API-Key'] = apiKey
      }

      const response = await fetch('/api/email/search', {
        method: 'POST',
        headers,
        body: JSON.stringify({ email: email.trim() })
      })

      const data = await response.json()

      if (response.ok) {
        setResults(data)
      } else {
        setError(data.error || 'Ошибка при поиске')
      }
    } catch (error) {
      setError('Ошибка соединения с сервером')
    } finally {
      setLoading(false)
    }
  }

  const loadDemo = async () => {
    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/email/demo')
      const data = await response.json()

      if (response.ok) {
        setResults(data)
        setEmail(data.email)
      } else {
        setError('Ошибка загрузки демо данных')
      }
    } catch (error) {
      setError('Ошибка соединения с сервером')
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const headers = {}
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`
      } else if (apiKey) {
        headers['X-API-Key'] = apiKey
      }

      const response = await fetch('/api/monitoring/stats/summary', { headers })
      const data = await response.json()

      if (response.ok) {
        setStats(data.summary)
        setShowStats(true)
      } else {
        setError('Ошибка загрузки статистики')
      }
    } catch (error) {
      setError('Ошибка соединения с сервером')
    }
  }

  const AuthModal = () => (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-96 max-w-md">
        <h2 className="text-xl font-bold mb-4">
          {authMode === 'login' ? 'Вход' : 'Регистрация'}
        </h2>
        
        <form onSubmit={(e) => {
          e.preventDefault()
          const formData = new FormData(e.target)
          const data = Object.fromEntries(formData)
          handleAuth(data)
        }}>
          <div className="space-y-4">
            <input
              name="username"
              type="text"
              placeholder="Имя пользователя"
              className="w-full p-2 border rounded"
              required
            />
            
            {authMode === 'register' && (
              <input
                name="email"
                type="email"
                placeholder="Email"
                className="w-full p-2 border rounded"
                required
              />
            )}
            
            <input
              name="password"
              type="password"
              placeholder="Пароль"
              className="w-full p-2 border rounded"
              required
            />
            
            {authMode === 'register' && (
              <select
                name="user_type"
                className="w-full p-2 border rounded"
                defaultValue="free"
              >
                <option value="free">Бесплатный</option>
                <option value="premium">Премиум</option>
                <option value="enterprise">Корпоративный</option>
              </select>
            )}
          </div>
          
          <div className="flex gap-2 mt-6">
            <button
              type="submit"
              className="flex-1 bg-blue-500 text-white py-2 rounded hover:bg-blue-600"
            >
              {authMode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </button>
            <button
              type="button"
              onClick={() => setShowAuthModal(false)}
              className="flex-1 bg-gray-300 text-gray-700 py-2 rounded hover:bg-gray-400"
            >
              Отмена
            </button>
          </div>
        </form>
        
        <div className="mt-4 text-center">
          <button
            onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
            className="text-blue-500 hover:underline"
          >
            {authMode === 'login' ? 'Нет аккаунта? Зарегистрироваться' : 'Есть аккаунт? Войти'}
          </button>
        </div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Email Search Service</h1>
              <p className="text-sm text-gray-600">Профессиональный поиск информации по email адресам</p>
            </div>
            
            <div className="flex items-center gap-4">
              {isAuthenticated ? (
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-600">
                    Привет, {userInfo?.username} ({userInfo?.user_type})
                  </span>
                  <button
                    onClick={loadStats}
                    className="text-sm bg-green-500 text-white px-3 py-1 rounded hover:bg-green-600"
                  >
                    Статистика
                  </button>
                  <button
                    onClick={logout}
                    className="text-sm bg-red-500 text-white px-3 py-1 rounded hover:bg-red-600"
                  >
                    Выйти
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setShowAuthModal(true)}
                  className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
                >
                  Войти / Регистрация
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-4xl mx-auto p-6">
        {/* Search Form */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex gap-4 mb-4">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Введите email адрес для поиска..."
              className="flex-1 p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              onKeyPress={(e) => e.key === 'Enter' && searchEmail()}
            />
            <button
              onClick={searchEmail}
              disabled={loading}
              className="bg-blue-500 text-white px-6 py-3 rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Поиск...' : 'Найти'}
            </button>
            <button
              onClick={loadDemo}
              disabled={loading}
              className="bg-green-500 text-white px-6 py-3 rounded-lg hover:bg-green-600 disabled:opacity-50"
            >
              Показать демо
            </button>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* Results */}
        {results && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold mb-4">Результаты поиска</h2>
            
            {/* Basic Info */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-2">Основная информация</h3>
              <div className="bg-gray-50 p-4 rounded-lg">
                <p><strong>Email:</strong> {results.email}</p>
                {results.basic_info?.owner_name && (
                  <p><strong>Владелец:</strong> {results.basic_info.owner_name}</p>
                )}
                {results.basic_info?.status && (
                  <span className={`inline-block px-2 py-1 rounded text-sm ${
                    results.basic_info.status === 'identified' ? 'bg-green-100 text-green-800' :
                    results.basic_info.status === 'partial_info' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {results.basic_info.status === 'identified' ? 'Идентифицирован' :
                     results.basic_info.status === 'partial_info' ? 'Частичная информация' :
                     'Неизвестен'}
                  </span>
                )}
              </div>
            </div>

            {/* Professional Info */}
            {results.professional_info && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Профессиональная информация</h3>
                <div className="bg-gray-50 p-4 rounded-lg">
                  {results.professional_info.position && (
                    <p><strong>Должность:</strong> {results.professional_info.position}</p>
                  )}
                  {results.professional_info.workplace && (
                    <p><strong>Место работы:</strong> {results.professional_info.workplace}</p>
                  )}
                  {results.professional_info.specialization && (
                    <p><strong>Специализация:</strong> {results.professional_info.specialization}</p>
                  )}
                </div>
              </div>
            )}

            {/* Scientific Identifiers */}
            {results.scientific_identifiers && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Научные идентификаторы</h3>
                <div className="bg-gray-50 p-4 rounded-lg">
                  {results.scientific_identifiers.orcid_id && (
                    <p><strong>ORCID ID:</strong> {results.scientific_identifiers.orcid_id}</p>
                  )}
                  {results.scientific_identifiers.spin_code && (
                    <p><strong>SPIN-код:</strong> {results.scientific_identifiers.spin_code}</p>
                  )}
                </div>
              </div>
            )}

            {/* Publications */}
            {results.publications && results.publications.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Публикации</h3>
                <div className="space-y-3">
                  {results.publications.map((pub, index) => (
                    <div key={index} className="bg-gray-50 p-4 rounded-lg">
                      <h4 className="font-medium">{pub.title}</h4>
                      <p className="text-sm text-gray-600">{pub.journal}</p>
                      {pub.authors && <p className="text-sm text-gray-600">Авторы: {pub.authors}</p>}
                      {pub.doi && <p className="text-sm text-blue-600">DOI: {pub.doi}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Research Interests */}
            {results.research_interests && results.research_interests.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Области научных интересов</h3>
                <div className="flex flex-wrap gap-2">
                  {results.research_interests.map((interest, index) => (
                    <span key={index} className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
                      {interest}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Conclusions */}
            {results.conclusions && results.conclusions.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Выводы</h3>
                <ul className="list-disc list-inside space-y-1">
                  {results.conclusions.map((conclusion, index) => (
                    <li key={index} className="text-gray-700">{conclusion}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Search Metadata */}
            {results.search_metadata && (
              <div className="mt-6 pt-4 border-t border-gray-200">
                <h3 className="text-sm font-semibold text-gray-600 mb-2">Метаданные поиска</h3>
                <div className="text-xs text-gray-500 space-y-1">
                  <p>Статус: {results.search_metadata.status}</p>
                  <p>Найдено результатов: {results.search_metadata.results_count || 0}</p>
                  <p>Метод поиска: {results.search_metadata.search_method || 'unknown'}</p>
                  {results.search_metadata.timestamp && (
                    <p>Время поиска: {new Date(results.search_metadata.timestamp * 1000).toLocaleString()}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Stats Modal */}
        {showStats && stats && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 w-96 max-w-md">
              <h2 className="text-xl font-bold mb-4">Статистика сервиса</h2>
              
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span>Запросов за 24ч:</span>
                  <span className="font-semibold">{stats.total_requests_24h}</span>
                </div>
                <div className="flex justify-between">
                  <span>Среднее время ответа:</span>
                  <span className="font-semibold">{stats.avg_response_time_ms}мс</span>
                </div>
                <div className="flex justify-between">
                  <span>Попаданий в кэш:</span>
                  <span className="font-semibold">{stats.cache_hit_rate_percent}%</span>
                </div>
                <div className="flex justify-between">
                  <span>Статус сервиса:</span>
                  <span className="font-semibold text-green-600">{stats.service_uptime}</span>
                </div>
              </div>
              
              <button
                onClick={() => setShowStats(false)}
                className="w-full mt-4 bg-gray-300 text-gray-700 py-2 rounded hover:bg-gray-400"
              >
                Закрыть
              </button>
            </div>
          </div>
        )}

        {/* Auth Modal */}
        {showAuthModal && <AuthModal />}
      </div>
    </div>
  )
}

export default EmailSearch

