import { createBrowserRouter, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import MainLayout from '@/components/layout/MainLayout'
import AuthGuard from '@/components/AuthGuard'
import LoadingSpinner from '@/components/common/LoadingSpinner'

// 页面组件懒加载
const Login = lazy(() => import('@/pages/login/Login'))
const Dashboard = lazy(() => import('@/pages/dashboard/Dashboard'))
const UserList = lazy(() => import('@/pages/user/UserList'))
const UserCreate = lazy(() => import('@/pages/user/UserCreate'))
const UserEdit = lazy(() => import('@/pages/user/UserEdit'))
const VideoList = lazy(() => import('@/pages/content/video/VideoList'))
const VideoDetail = lazy(() => import('@/pages/content/video/VideoDetail'))
const AudioList = lazy(() => import('@/pages/content/audio/AudioList'))
const ImageList = lazy(() => import('@/pages/content/image/ImageList'))
const SystemMonitor = lazy(() => import('@/pages/system/SystemMonitor'))
const Settings = lazy(() => import('@/pages/settings/Settings'))
const NotFound = lazy(() => import('@/pages/error/NotFound'))

const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <Suspense fallback={<LoadingSpinner />}>
        <Login />
      </Suspense>
    ),
  },
  {
    path: '/',
    element: (
      <AuthGuard>
        <MainLayout />
      </AuthGuard>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: (
          <Suspense fallback={<LoadingSpinner />}>
            <Dashboard />
          </Suspense>
        ),
      },
      {
        path: 'user',
        children: [
          {
            index: true,
            element: (
              <Suspense fallback={<LoadingSpinner />}>
                <UserList />
              </Suspense>
            ),
          },
          {
            path: 'create',
            element: (
              <Suspense fallback={<LoadingSpinner />}>
                <UserCreate />
              </Suspense>
            ),
          },
          {
            path: 'edit/:id',
            element: (
              <Suspense fallback={<LoadingSpinner />}>
                <UserEdit />
              </Suspense>
            ),
          },
        ],
      },
      {
        path: 'content',
        children: [
          {
            path: 'video',
            children: [
              {
                index: true,
                element: (
                  <Suspense fallback={<LoadingSpinner />}>
                    <VideoList />
                  </Suspense>
                ),
              },
              {
                path: 'detail/:id',
                element: (
                  <Suspense fallback={<LoadingSpinner />}>
                    <VideoDetail />
                  </Suspense>
                ),
              },
            ],
          },
          {
            path: 'audio',
            element: (
              <Suspense fallback={<LoadingSpinner />}>
                <AudioList />
              </Suspense>
            ),
          },
          {
            path: 'image',
            element: (
              <Suspense fallback={<LoadingSpinner />}>
                <ImageList />
              </Suspense>
            ),
          },
        ],
      },
      {
        path: 'system/monitor',
        element: (
          <Suspense fallback={<LoadingSpinner />}>
            <SystemMonitor />
          </Suspense>
        ),
      },
      {
        path: 'settings',
        element: (
          <Suspense fallback={<LoadingSpinner />}>
            <Settings />
          </Suspense>
        ),
      },
    ],
  },
  {
    path: '*',
    element: (
      <Suspense fallback={<LoadingSpinner />}>
        <NotFound />
      </Suspense>
    ),
  },
])

export default router
