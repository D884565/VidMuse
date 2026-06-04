function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">控制面板</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-6">
          <h3 className="text-gray-400 text-sm mb-2">总视频数</h3>
          <p className="text-3xl font-bold">0</p>
        </div>
        <div className="card p-6">
          <h3 className="text-gray-400 text-sm mb-2">总音频数</h3>
          <p className="text-3xl font-bold">0</p>
        </div>
        <div className="card p-6">
          <h3 className="text-gray-400 text-sm mb-2">总图片数</h3>
          <p className="text-3xl font-bold">0</p>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
