import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { PushProvider } from '@/contexts/PushContext'
import './styles/globals.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <PushProvider>
      <RouterProvider router={router} />
    </PushProvider>
  </StrictMode>,
)
