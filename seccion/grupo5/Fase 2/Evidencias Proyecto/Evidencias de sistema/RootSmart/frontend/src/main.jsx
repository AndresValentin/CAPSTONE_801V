import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './ios.css'
import App from './App.jsx'
import { aplicarIos, aplicarTema, iosGuardado, temaGuardado } from './lib/tema.js'

aplicarTema(temaGuardado())
aplicarIos(iosGuardado())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
