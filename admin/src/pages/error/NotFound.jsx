import { useNavigate } from 'react-router-dom'

function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-4">
      <h1 className="text-9xl font-bold text-primary/10">404</h1>
      <div className="text-center mt-8">
        <h2 className="text-2xl font-bold text-gray-500 mb-2">页面不存在</h2>
        <p className="text-gray-300 mb-8">抱歉，您访问的页面不存在或已被移动</p>
        <button
          onClick={() => navigate('/dashboard')}
          className="btn-primary"
        >
          返回首页
        </button>
      </div>
    </div>
  )
}

export default NotFound