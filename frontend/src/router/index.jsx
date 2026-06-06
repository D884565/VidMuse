import { createBrowserRouter } from 'react-router-dom'
import App from '../App.jsx'
import MainLayout from '../components/Layout/MainLayout.jsx'
import AdminLayout from '../components/Admin/Layout/AdminLayout.jsx'
import AuthGuard from '../components/AuthGuard.jsx'
import Dashboard from '../pages/Admin/Dashboard.jsx'
import UserManagement from '../pages/Admin/UserManagement.jsx'
import ContentManagement from '../pages/Admin/ContentManagement.jsx'
import SystemMonitor from '../pages/Admin/SystemMonitor.jsx'
import TemplateManagement from '../pages/Admin/TemplateManagement.jsx'
import CategoryManagement from '../pages/Admin/CategoryManagement.jsx'
import AssetManagement from '../pages/Admin/AssetManagement.jsx'
import VideoLibrary from '../pages/Admin/VideoLibrary.jsx'
import InspirationTemplate from '../pages/Admin/InspirationTemplate.jsx'
import TraceManagement from '../pages/Admin/TraceManagement.jsx'
import SystemTraceManagement from '../pages/Admin/SystemTraceManagement.jsx'
import NotFound from '../pages/NotFound.jsx'
import Forbidden from '../pages/Forbidden.jsx'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        index: true,
        element: <MainLayout />
      }
    ]
  },
  {
    path: '/admin',
    element: (
      <AuthGuard requiredRole="admin">
        <AdminLayout />
      </AuthGuard>
    ),
    children: [
      {
        index: true,
        element: <Dashboard />
      },
      {
        path: 'dashboard',
        element: <Dashboard />
      },
      {
        path: 'users',
        element: <UserManagement />
      },
      {
        path: 'content',
        element: <ContentManagement />
      },
      {
        path: 'system',
        element: <SystemMonitor />
      },
      {
        path: 'templates',
        element: <TemplateManagement />
      },
      {
        path: 'categories',
        element: <CategoryManagement />
      },
      {
        path: 'assets',
        element: <AssetManagement />
      },
      {
        path: 'videos',
        element: <VideoLibrary />
      },
      {
        path: 'inspiration',
        element: <InspirationTemplate />
      },
      {
        path: 'traces',
        element: <TraceManagement />
      },
      {
        path: 'system-traces',
        element: <SystemTraceManagement />
      }
    ]
  },
  {
    path: '/403',
    element: <Forbidden />
  },
  {
    path: '*',
    element: <NotFound />
  }
])
