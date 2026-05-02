from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
      <head><title>Kingdom 4</title></head>
      <body>
        <h1>Kingdom 4 Dashboard</h1>
        <p>This is the web UI for your local Kingdom.</p>
        <ul>
          <li><a href="/status">Commander status (JSON)</a></li>
          <li><a href="/docs">API docs (Swagger)</a></li>
        </ul>
      </body>
    </html>
    """
