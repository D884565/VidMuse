import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff } from 'lucide-react'
import useAuthStore from '@/store/authStore'
import LoadingSpinner from '@/components/common/LoadingSpinner'

const loginSchema = z.object({
  username: z.string().min(1, '请输入用户名'),
  password: z.string().min(6, '密码长度不能少于6位'),
  remember: z.boolean().optional(),
})

function Login() {
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const navigate = useNavigate()
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
  const login = useAuthStore((state) => state.login)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      username: '',
      password: '',
      remember: false,
    },
  })

  if (isLoggedIn) {
    return <Navigate to="/dashboard" replace />
  }

  const onSubmit = async (data) => {
    setLoading(true)
    setErrorMessage('')

    try {
      const result = await login(data)
      if (result.success) {
        navigate('/dashboard')
      } else {
        setErrorMessage(result.message)
      }
    } catch (error) {
      setErrorMessage('登录失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-primary/5 to-primary/10 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          {/* 标题区域 */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-500 mb-2">欢迎回来</h1>
            <p className="text-gray-300">登录 VidMuse 管理后台</p>
          </div>

          {/* 错误提示 */}
          {errorMessage && (
            <div className="mb-6 p-3 bg-danger/10 border border-danger/20 rounded-md text-danger text-sm">
              {errorMessage}
            </div>
          )}

          {/* 登录表单 */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">
                用户名
              </label>
              <input
                {...register('username')}
                type="text"
                placeholder="请输入用户名"
                className={`input ${errors.username ? 'border-danger focus:ring-danger/50 focus:border-danger' : ''}`}
              />
              {errors.username && (
                <p className="mt-1 text-sm text-danger">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-500 mb-1">
                密码
              </label>
              <div className="relative">
                <input
                  {...register('password')}
                  type={showPassword ? 'text' : 'password'}
                  placeholder="请输入密码"
                  className={`input pr-10 ${errors.password ? 'border-danger focus:ring-danger/50 focus:border-danger' : ''}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-300 hover:text-gray-400"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-danger">{errors.password.message}</p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center">
                <input
                  {...register('remember')}
                  type="checkbox"
                  className="rounded border-gray-200 text-primary focus:ring-primary/50"
                />
                <span className="ml-2 text-sm text-gray-400">记住我</span>
              </label>
              <a href="#" className="text-sm text-primary hover:text-primary/80">
                忘记密码?
              </a>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 flex items-center justify-center"
            >
              {loading ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  登录中...
                </>
              ) : (
                '登录'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default Login
