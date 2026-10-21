# ⚡ Photon — Real-time WebSocket Stock Ticker

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![WebSocket](https://img.shields.io/badge/WebSocket-Standard%20API-orange.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Photon** is a high-performance, real-time stock ticker web application engineered with a **Python FastAPI** backend and a responsive, accessible **vanilla HTML5/CSS3/JavaScript** frontend. Photon streams live stock price updates directly to connected browsers via persistent WebSockets without requiring manual page refreshes.

The project works straight out of the box with an asynchronous simulated market data streamer, requiring **no API keys, no paid subscriptions, and zero external financial account setups**.

---

## 📌 Table of Contents

- [Features](#-features)
- [Architecture & Data Flow](#-architecture--data-flow)
- [Project Directory Structure](#-project-directory-structure)
- [Technology Stack](#-technology-stack)
- [Simulated Data Notice](#-simulated-data-notice)
- [Quick Start Guide (Windows)](#-quick-start-guide-windows)
- [REST API Endpoints](#-rest-api-endpoints)
- [WebSocket API & Message Protocol](#-websocket-api--message-protocol)
- [Automated Testing](#-automated-testing)
- [Optional Real Financial API Integration](#-optional-real-financial-api-integration)
- [Deployment Readiness](#-deployment-readiness)
- [GitHub Publishing Guide](#-github-publishing-guide)
- [Future Roadmap](#-future-roadmap)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Features

- **⚡ Real-time WebSocket Streaming:** Low-latency bidirectional communication pushes live price ticks to connected clients every second.
- **📈 Six Demonstration Stocks:** Pre-configured with realistic baseline prices:
  - `AAPL` — Apple Inc.
  - `GOOGL` — Alphabet Inc.
  - `MSFT` — Microsoft Corporation
  - `AMZN` — Amazon.com Inc.
  - `TSLA` — Tesla Inc.
  - `NVDA` — NVIDIA Corporation
- **🕯️ Interactive Candlestick & Line Chart Engine:**
  - Clicking any stock card opens a comprehensive **Market Details & Chart Dialog**.
  - **User Choice Options:** Seamless one-click switching between **Japanese Candlesticks** (`🕯️ Candlesticks`) and **Continuous Area / Line Graph** (`📈 Line Graph`).
  - **Dynamic Live Candle Updates:** Incoming WebSocket ticks dynamically mutate the current active candle in real time (high, low, close, volume).
  - **Interactive Crosshairs & Hover HUD:** Moving the cursor over the chart displays high-precision dashed crosshairs, price tags, and an instant OHLCV metric readout.
- **📊 In-depth Fundamentals & Valuation Metrics:**
  - Comprehensive financial statistics: Day Range (Low/High), Day Open, Trading Volume, Market Capitalization, P/E Ratio (TTM), and 52-Week Range (Low/High).
  - Full company profile and operational description.
- **🎯 Dynamic Price Movement & Flash Indicators:**
  - Micro-animations flash **emerald green** when a stock ticks upward.
  - Micro-animations flash **crimson red** when a stock ticks downward.
  - Visual delta indicators (`▲`, `▼`, `•`) display absolute change and percentage change.
- **🎛️ Independent Client Subscriptions:**
  - Users can select or deselect specific stocks dynamically via interactive chips.
  - "Select All" and "Deselect All" convenience actions.
  - Changes take effect immediately via WebSocket without refreshing the webpage.
  - Connections with no explicit selection receive all stocks by default.
- **🔍 Instant Live Search & Filtering:**
  - Filter active stocks by symbol (e.g., `AAPL`) or company name (e.g., `Tesla`).
  - Search filtering only alters DOM visibility and preserves active WebSocket subscriptions.
- **🔄 Fault-Tolerant Reconnection Engine:**
  - Automatic reconnection using exponential backoff with jitter if connection drops.
  - Single active reconnection timer preventing duplicate sockets or connection storms.
  - Visual status pill (`Connected`, `Connecting`, `Reconnecting`, `Disconnected`).
  - Manual "Reconnect Now" button.
- **🛡️ Clean Modular Architecture:**
  - Strict separation of concerns between data providers, service layer, connection management, and routing.
  - Ready for future integration with real market providers (e.g., Alpaca, Finnhub).
- **🧪 100% Automated Test Coverage:**
  - Comprehensive `pytest` suite verifying REST endpoints, models, WebSocket lifecycle, subscriptions, and multi-client broadcast isolation.

---

## 🏛️ Architecture & Data Flow

```text
┌─────────────────────────────────────────────────────────────┐
│                      Browser Dashboard                      │
│   (HTML5 + CSS3 + Vanilla JS + Native WebSocket Client)     │
└──────────────────────────┬───────▲──────────────────────────┘
                           │       │
              HTTP GET /   │       │ WS /ws (Bi-directional JSON)
             Static Assets │       │ Snapshot & Selective Ticks
                           ▼       │
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                    │
│                                                             │
│   ┌────────────────────┐          ┌─────────────────────┐   │
│   │   REST Endpoints   │          │  ConnectionManager  │   │
│   │   - GET /          │          │  - Client registry  │   │
│   │   - GET /api/stocks│          │  - Subscriptions    │   │
│   │   - GET /api/health│          │  - Safe broadcast   │   │
│   └────────────────────┘          └──────────▲──────────┘   │
│                                              │              │
│                                   Tick Event │              │
│                           ┌──────────────────┴──────────┐   │
│                           │         StockService        │   │
│                           │   (Background Async Loop)   │   │
│                           └──────────▲──────────────────┘   │
│                                      │                      │
│                           Generate   │ Next Update          │
│                           ┌──────────┴──────────────────┐   │
│                           │   BaseStockProvider (ABC)   │   │
│                           │   └── MockStockProvider     │   │
│                           └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Directory Structure

```text
photon-stock-ticker/
├── app/
│   ├── __init__.py               # Application package marker
│   ├── main.py                   # FastAPI server, endpoints, and lifecycle
│   ├── connection_manager.py     # Multi-client WebSocket & subscription manager
│   ├── stock_service.py          # Stock service coordinator & background streamer
│   ├── models.py                 # Pydantic schemas (StockData, Messages, Requests)
│   └── providers/
│       ├── __init__.py           # Providers package
│       ├── base.py               # Abstract BaseStockProvider contract
│       └── mock_provider.py      # Asynchronous simulated stock price generator
├── static/
│   ├── css/
│   │   └── styles.css            # Dark financial dashboard styles & flash animations
│   └── js/
│       └── app.js                # Vanilla JS WebSocket controller & DOM engine
├── templates/
│   └── index.html                # Semantic HTML5 dashboard layout
├── tests/
│   ├── test_api.py               # REST API & model validation tests
│   └── test_websocket.py         # WebSocket connection & broadcast unit tests
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusions (.venv, __pycache__, .env, etc.)
├── pytest.ini                    # Pytest configuration and pythonpath
├── requirements.txt              # Production and test dependencies
├── run.py                        # Cross-platform application entrypoint
└── README.md                     # Comprehensive project documentation
```

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Backend Framework** | [FastAPI](https://fastapi.tiangolo.com/) (0.110+) | High-performance ASGI web framework |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) | Async HTTP & WebSocket server |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Strict data schemas and serialization |
| **Async Engine** | Python `asyncio` | Non-blocking periodic market simulation loop |
| **Frontend UI** | Semantic HTML5 & CSS3 | Dark-theme, responsive financial layout |
| **Frontend Logic** | Vanilla JavaScript (ES6+) | Native WebSocket API, zero external JS libraries |
| **Testing** | [pytest](https://pytest.org/) & `httpx` | Automated unit, REST, and WebSocket tests |
| **Version Control** | Git & GitHub | Source code hosting and release management |

---

## ⚠️ Simulated Data Notice

> **IMPORTANT DISCLAIMER**
> 
> All stock prices, corporate metrics, and fluctuations presented in **Photon** are synthetically generated by an internal Python stochastic algorithm for educational, demonstration, and software engineering portfolio purposes.
> 
> **Never use this application or its output for real-world trading, investment decisions, or financial advice.**

---

## 💻 Quick Start Guide (Windows)

Follow these steps to set up and run Photon on Windows.

### Prerequisites
- Python **3.11 or newer** installed ([Download Python](https://www.python.org/downloads/)).
- Git installed ([Download Git](https://git-scm.com/download/win)).

### 1. Clone or Open the Workspace
Open PowerShell or Command Prompt in the project folder:
```powershell
cd "d:\photon stock market"
```

### 2. Create and Activate a Virtual Environment

**Using PowerShell:**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

*(Note: If PowerShell displays an `Execution_Policies` restriction, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the activate command again).*

**Using Command Prompt (cmd.exe):**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment (Optional)
Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

### 5. Launch the Application
```powershell
python run.py
```

Console Output:
```text
============================================================
  [*] Photon - Real-time WebSocket Stock Ticker
============================================================
  * Local Dashboard:  http://127.0.0.1:8000
  * REST API Stocks:  http://127.0.0.1:8000/api/stocks
  * REST API Health:  http://127.0.0.1:8000/api/health
  * WebSocket Stream: ws://127.0.0.1:8000/ws
  * Auto-Reload:      True
============================================================
  Press Ctrl+C to stop the server.
```

### 6. Open the Dashboard in Your Browser
Navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

To stop the server, press `Ctrl + C` in the terminal.

---

## 🌐 REST API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves the interactive stock dashboard |
| `GET` | `/api/stocks` | Returns the current JSON snapshot of all 6 tracked stocks |
| `GET` | `/api/stocks/{symbol}` | Returns in-depth corporate fundamentals, valuation metrics, and OHLC candlestick data |
| `GET` | `/api/health` | Returns health status, active connections, and provider information |

### Example Response: `GET /api/stocks`
```json
[
  {
    "symbol": "AAPL",
    "company": "Apple Inc.",
    "price": 182.50,
    "previous_price": 181.75,
    "change": 0.75,
    "change_percent": 0.4127,
    "currency": "USD",
    "is_simulated": true,
    "timestamp": "2026-10-21T14:30:00Z"
  }
]
```

### Example Response: `GET /api/health`
```json
{
  "status": "ok",
  "provider": "mock",
  "is_simulated": true,
  "active_connections": 1,
  "tracked_stocks": 6,
  "timestamp": "2026-10-21T14:30:05Z"
}
```

---

## 📡 WebSocket API & Message Protocol

### Connection URL
```text
ws://127.0.0.1:8000/ws
```

### Message Types Sent by Server

#### 1. Initial Snapshot (`initial_snapshot`)
Sent immediately when a client opens a connection:
```json
{
  "type": "initial_snapshot",
  "timestamp": "2026-10-21T14:30:00Z",
  "is_simulated": true,
  "data": [
    {
      "symbol": "AAPL",
      "company": "Apple Inc.",
      "price": 182.50,
      "previous_price": 182.50,
      "change": 0.0,
      "change_percent": 0.0,
      "currency": "USD",
      "is_simulated": true,
      "timestamp": "2026-10-21T14:30:00Z"
    }
  ]
}
```

#### 2. Stock Update (`stock_update`)
Broadcast to subscribed clients whenever a price tick occurs:
```json
{
  "type": "stock_update",
  "timestamp": "2026-10-21T14:30:01Z",
  "data": {
    "symbol": "NVDA",
    "company": "NVIDIA Corporation",
    "price": 128.60,
    "previous_price": 127.85,
    "change": 0.75,
    "change_percent": 0.5866,
    "currency": "USD",
    "is_simulated": true,
    "timestamp": "2026-10-21T14:30:01Z"
  }
}
```

#### 3. Subscription Status (`subscription_status`)
Acknowledgement sent back after a client alters their subscriptions:
```json
{
  "type": "subscription_status",
  "timestamp": "2026-10-21T14:30:02Z",
  "status": "success",
  "subscribed_symbols": ["AAPL", "NVDA"],
  "message": "Subscription updated to ['AAPL', 'NVDA']"
}
```

### Messages Sent by Client

Clients update their subscriptions dynamically over the open socket:
```json
// Set full subscription list
{
  "action": "set",
  "symbols": ["AAPL", "TSLA"]
}

// Add symbols incrementally
{
  "action": "subscribe",
  "symbols": ["MSFT"]
}

// Remove symbols incrementally
{
  "action": "unsubscribe",
  "symbols": ["AAPL"]
}
```

---

## 🧪 Automated Testing

Photon includes an automated test suite powered by `pytest` and `httpx`.

### Run All Tests
With your virtual environment active, run:
```powershell
pytest -v
```

### Test Coverage Highlights
- ✅ `test_homepage_availability`: Confirms `GET /` returns HTTP 200, renders all stock symbols, and includes the simulated data disclaimer badge.
- ✅ `test_api_stocks_response_structure`: Confirms `GET /api/stocks` conforms to the Pydantic `StockData` model and verifies price bounds.
- ✅ `test_api_health_response`: Confirms `GET /api/health` reports status, provider name, and connection counts.
- ✅ `test_mock_provider_price_generation`: Confirms the mock generator produces non-negative, non-zero prices and calculated movement deltas.
- ✅ `test_websocket_connection_and_initial_snapshot`: Tests client handshake and immediate initial snapshot reception.
- ✅ `test_websocket_subscription_set_action`: Tests setting selective subscriptions over WebSocket.
- ✅ `test_websocket_subscription_incremental`: Tests subscribing and unsubscribing incrementally.
- ✅ `test_websocket_invalid_subscription_message`: Tests server resiliency when receiving malformed JSON or unsupported actions.
- ✅ `test_websocket_unknown_stock_symbols`: Tests graceful warning handling when a user requests an unrecognized ticker symbol.
- ✅ `test_multiple_simultaneous_connections`: Verifies that multiple browser clients connect concurrently and maintain independent subscriptions.
- ✅ `test_connection_manager_broadcast_and_filtering`: Unit tests `ConnectionManager` selective broadcast logic to ensure updates only route to subscribed clients.

---

## 🔌 Optional Real Financial API Integration

Photon features a clean provider abstraction designed around `BaseStockProvider`:

```python
# app/providers/base.py
class BaseStockProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...
    @property
    @abstractmethod
    def is_simulated(self) -> bool: ...
    @abstractmethod
    def get_initial_stocks(self) -> Dict[str, StockData]: ...
    @abstractmethod
    def get_current_stocks(self) -> Dict[str, StockData]: ...
    @abstractmethod
    async def generate_next_update(self) -> Optional[StockData]: ...
```

### Integrating Alpaca or Finnhub in the Future:
1. Create `app/providers/alpaca_provider.py` (or `finnhub_provider.py`) implementing `BaseStockProvider`.
2. Connect to the provider's official WebSocket stream (e.g., Alpaca Market Data v2 WebSocket).
3. Read credentials securely from environment variables (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`).
4. Set `STOCK_PROVIDER=alpaca` in your `.env` file.
5. In `app/stock_service.py`, instantiate `AlpacaStockProvider` when `STOCK_PROVIDER == "alpaca"`.
6. If credentials are missing or the external API is unreachable, Photon automatically falls back to `MockStockProvider` and logs a clear warning.

---

## 🚀 Deployment Readiness

When deploying Photon to production:

### 1. Hosting Environment Requirements
- **Persistent WebSocket Support:** You must choose a platform that supports continuous, long-lived WebSocket connections (e.g., Render, Railway, DigitalOcean App Platform, Fly.io, AWS ECS, or Google Cloud Run with session affinity/WebSocket enabled).
- **Static Hosting Incompatibility:** Do not deploy Photon to static-only hosting services (such as GitHub Pages or Netlify static hosting) because Photon requires an active Python ASGI backend process.

### 2. Environment Variables in Production
Configure the following in your hosting provider's dashboard:
- `PORT`: Automatically provided by platforms like Render or Railway.
- `HOST`: Set to `0.0.0.0` for containerized environments.
- `DEBUG`: Set to `False`.

### 3. Production Start Command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```
*(Note: Use a single worker process or an external message broker like Redis Pub/Sub if scaling to multiple workers, so that WebSocket broadcasts reach clients on all worker processes).*

---

## 🐙 GitHub Publishing Guide

Follow these steps to publish this repository to GitHub:

### Step 1: Create a New Empty Repository
1. Visit **[https://github.com/new](https://github.com/new)**.
2. Enter repository name: `photon-stock-ticker`.
3. Choose **Public** (or **Private**).
4. **Do NOT** initialize with a README, .gitignore, or License (these are already configured locally).
5. Click **Create repository**.

### Step 2: Push Local Repository to GitHub
Replace `YOUR_USERNAME` with your actual GitHub username:

```powershell
# 1. Check git status to ensure working tree is clean
git status

# 2. Stage all project files
git add .

# 3. Commit the project
git commit -m "Initial commit: Photon - Real-time WebSocket Stock Ticker"

# 4. Set default branch to main
git branch -M main

# 5. Add remote origin (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/photon-stock-ticker.git

# 6. Push to GitHub
git push -u origin main
```

---

## 🗺️ Future Roadmap

- [ ] **Interactive Candlestick & Sparkline Charts:** Integrate Lightweight Charts or Chart.js to visualize historical tick trends.
- [ ] **React Frontend Option (Week 4 Plan):** Provide an optional React + Vite dashboard variant while retaining the same FastAPI WebSocket backend.
- [ ] **User Authentication & Custom Portfolios:** Add user accounts with saved watchlists and custom alert thresholds.
- [ ] **Sound Alerts & Haptic Ticks:** Optional audio notification toggle for price break-outs and major percentage swings.

---

## 🔧 Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'app'` | Python cannot find root package | Run commands from workspace root `d:\photon stock market` or ensure `pythonpath = .` in `pytest.ini`. |
| PowerShell script execution error on `.venv\Scripts\Activate.ps1` | Windows ExecutionPolicy restriction | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in your PowerShell session. |
| `WebSocket connection failed` in browser | Server is not running or port 8000 is occupied | Verify `python run.py` is running and check console for any port conflicts. |
| Port 8000 already in use | Another service is using port 8000 | Set `PORT=8080` in `.env` and restart `python run.py`. |

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
