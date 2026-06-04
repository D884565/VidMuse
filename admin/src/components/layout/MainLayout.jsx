import { Outlet } from 'react-router-dom'

function MainLayout() {
  return (
    <div className="min-h-screen">
      {/* TODO: Implement sidebar, header, etc. */}
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  )
}

export default MainLayout
