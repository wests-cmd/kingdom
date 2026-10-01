import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App"
import "./styles/app.css"
import {initializeAppearance} from './components/common/AppearanceProvider'

initializeAppearance()

ReactDOM.createRoot(
  document.getElementById("root")
).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
