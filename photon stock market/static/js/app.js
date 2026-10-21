/**
 * Photon — Real-time WebSocket Stock Ticker Frontend Controller
 * 
 * Features:
 * - WebSocket lifecycle management with exponential backoff auto-reconnect
 * - Independent per-client stock subscriptions & live search filtering
 * - Targeted DOM element updating with green/red micro-flash indicators
 * - Interactive Stock Details dialog with full financial metrics
 * - Realistic HTML5 Canvas Chart Engine supporting both Candlestick and Line/Area modes
 * - Dynamic live-candle streaming and real-time chart updating
 */

(function () {
    'use strict';

    // Application State
    const state = {
        ws: null,
        reconnectTimer: null,
        reconnectAttempts: 0,
        maxReconnectDelayMs: 10000,
        baseReconnectDelayMs: 1000,
        isUserIntentionalDisconnect: false,
        allTrackedSymbols: new Set(),
        subscribedSymbols: new Set(),
        searchQuery: '',
        lastPrices: new Map(), // symbol -> numeric price

        // Detail Modal & Interactive Chart State
        activeDetailSymbol: null,
        activeDetailData: null,
        activeCandles: [],
        chartMode: localStorage.getItem('photon_chart_mode') || 'candles', // 'candles' or 'graph'
        hoveredCandleIndex: null,
        crosshairPos: null,
    };

    // DOM Elements Cache
    const dom = {
        connectionDot: document.getElementById('connectionDot'),
        connectionStatus: document.getElementById('connectionStatus'),
        lastUpdated: document.getElementById('lastUpdated'),
        trackedCount: document.getElementById('trackedCount'),
        subCount: document.getElementById('subCount'),
        reconnectBanner: document.getElementById('reconnectBanner'),
        reconnectBannerText: document.getElementById('reconnectBannerText'),
        manualReconnectBtn: document.getElementById('manualReconnectBtn'),
        stockSearchInput: document.getElementById('stockSearchInput'),
        clearSearchBtn: document.getElementById('clearSearchBtn'),
        selectAllBtn: document.getElementById('selectAllBtn'),
        deselectAllBtn: document.getElementById('deselectAllBtn'),
        chipsContainer: document.getElementById('symbolChipsContainer'),
        stocksGrid: document.getElementById('stocksGrid'),
        emptyState: document.getElementById('emptyState'),
        emptyQueryText: document.getElementById('emptyQueryText'),
        resetSearchBtn: document.getElementById('resetSearchBtn'),
        filteredResultsLabel: document.getElementById('filteredResultsLabel'),

        // Modal Elements
        stockModal: document.getElementById('stockModal'),
        closeModalBtn: document.getElementById('closeModalBtn'),
        modalStockSymbol: document.getElementById('modalStockSymbol'),
        modalCompanyName: document.getElementById('modalCompanyName'),
        modalSectorPill: document.getElementById('modalSectorPill'),
        modalCurrentPrice: document.getElementById('modalCurrentPrice'),
        modalMovement: document.getElementById('modalMovement'),
        modalArrow: document.getElementById('modalArrow'),
        modalChange: document.getElementById('modalChange'),
        modalChangePercent: document.getElementById('modalChangePercent'),
        modalDayLow: document.getElementById('modalDayLow'),
        modalDayHigh: document.getElementById('modalDayHigh'),
        modalDayOpen: document.getElementById('modalDayOpen'),
        modalVolume: document.getElementById('modalVolume'),
        modalMarketCap: document.getElementById('modalMarketCap'),
        modalPeRatio: document.getElementById('modalPeRatio'),
        modal52Low: document.getElementById('modal52Low'),
        modal52High: document.getElementById('modal52High'),
        modalAboutName: document.getElementById('modalAboutName'),
        modalCompanyDesc: document.getElementById('modalCompanyDesc'),

        // Chart Viewport Elements
        chartModeCandles: document.getElementById('chartModeCandles'),
        chartModeGraph: document.getElementById('chartModeGraph'),
        chartViewport: document.getElementById('chartViewport'),
        stockCanvas: document.getElementById('stockCanvas'),
        chartHud: document.getElementById('chartHud'),
        hudOpen: document.getElementById('hudOpen'),
        hudHigh: document.getElementById('hudHigh'),
        hudLow: document.getElementById('hudLow'),
        hudClose: document.getElementById('hudClose'),
        hudVol: document.getElementById('hudVol'),
        hudBadge: document.getElementById('hudBadge'),
        chartCrosshairTooltip: document.getElementById('chartCrosshairTooltip'),
    };

    /**
     * Determine WebSocket protocol and connection URL
     */
    function getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws`;
    }

    /**
     * Format a number to 2 decimal places with comma separation
     */
    function formatCurrency(num) {
        return Number(num).toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    /**
     * Format signed movement number (e.g., +1.25 or -0.50)
     */
    function formatSigned(num) {
        const val = Number(num);
        const sign = val > 0 ? '+' : '';
        return `${sign}${val.toFixed(2)}`;
    }

    /**
     * Format large integer volumes with compact or comma notation
     */
    function formatVolume(num) {
        const val = Number(num);
        if (val >= 1e9) return (val / 1e9).toFixed(2) + ' B';
        if (val >= 1e6) return (val / 1e6).toFixed(2) + ' M';
        if (val >= 1e3) return (val / 1e3).toFixed(1) + ' K';
        return val.toLocaleString();
    }

    /**
     * Update connection state and visual indicators
     */
    function setConnectionStatus(status, message) {
        if (!dom.connectionDot || !dom.connectionStatus) return;

        dom.connectionDot.className = `status-dot ${status.toLowerCase()}`;
        dom.connectionStatus.textContent = message || status;

        if (status === 'connected') {
            dom.reconnectBanner.classList.add('hidden');
        }
    }

    /**
     * Initialize WebSocket connection with robust error & reconnection handling
     */
    function initWebSocket() {
        if (state.reconnectTimer) {
            clearTimeout(state.reconnectTimer);
            state.reconnectTimer = null;
        }

        if (state.ws) {
            try {
                state.ws.onopen = null;
                state.ws.onclose = null;
                state.ws.onerror = null;
                state.ws.onmessage = null;
                state.ws.close();
            } catch (e) {
                console.warn('Cleanup error on previous socket:', e);
            }
            state.ws = null;
        }

        const wsUrl = getWebSocketUrl();
        setConnectionStatus('connecting', 'Connecting...');

        try {
            state.ws = new WebSocket(wsUrl);
        } catch (err) {
            console.error('Failed to create WebSocket instance:', err);
            scheduleReconnect();
            return;
        }

        state.ws.onopen = function () {
            console.log('✅ WebSocket connection established.');
            state.reconnectAttempts = 0;
            setConnectionStatus('connected', 'Connected');

            if (state.subscribedSymbols.size > 0 && state.subscribedSymbols.size !== state.allTrackedSymbols.size) {
                sendSubscriptionUpdate(Array.from(state.subscribedSymbols));
            }
        };

        state.ws.onmessage = function (event) {
            try {
                const message = JSON.parse(event.data);
                handleIncomingMessage(message);
            } catch (err) {
                console.error('Failed to parse WebSocket JSON payload:', err, event.data);
            }
        };

        state.ws.onclose = function (event) {
            console.warn(`WebSocket connection closed (code=${event.code}, reason=${event.reason || 'none'})`);
            setConnectionStatus('disconnected', 'Disconnected');
            if (!state.isUserIntentionalDisconnect) {
                scheduleReconnect();
            }
        };

        state.ws.onerror = function (error) {
            console.error('WebSocket connection error:', error);
            setConnectionStatus('disconnected', 'Connection Error');
        };
    }

    /**
     * Schedule reconnection using exponential backoff
     */
    function scheduleReconnect() {
        if (state.reconnectTimer) return;

        state.reconnectAttempts++;
        const factor = Math.pow(1.5, Math.min(state.reconnectAttempts - 1, 8));
        const rawDelay = state.baseReconnectDelayMs * factor;
        const delay = Math.min(Math.round(rawDelay), state.maxReconnectDelayMs);
        const delaySeconds = Math.round(delay / 1000);

        setConnectionStatus('reconnecting', `Reconnecting in ${delaySeconds}s...`);
        dom.reconnectBanner.classList.remove('hidden');
        dom.reconnectBannerText.textContent = `Connection lost. Reconnecting in ${delaySeconds}s (attempt ${state.reconnectAttempts})...`;

        state.reconnectTimer = setTimeout(function () {
            state.reconnectTimer = null;
            initWebSocket();
        }, delay);
    }

    /**
     * Handle incoming parsed WebSocket messages
     */
    function handleIncomingMessage(msg) {
        if (!msg || !msg.type) return;

        switch (msg.type) {
            case 'initial_snapshot':
                handleInitialSnapshot(msg);
                break;
            case 'stock_update':
                handleStockUpdate(msg.data);
                break;
            case 'subscription_status':
                handleSubscriptionStatus(msg);
                break;
            case 'error':
                console.error('Backend returned WebSocket error:', msg.error);
                break;
            default:
                console.warn('Unknown message type received:', msg.type);
        }
    }

    /**
     * Handle initial snapshot upon connection
     */
    function handleInitialSnapshot(msg) {
        if (!Array.isArray(msg.data)) return;

        state.allTrackedSymbols.clear();
        msg.data.forEach(function (stock) {
            state.allTrackedSymbols.add(stock.symbol);
            state.lastPrices.set(stock.symbol, stock.price);
            if (state.subscribedSymbols.size === 0) {
                state.subscribedSymbols.add(stock.symbol);
            }
            updateStockCard(stock, false);
        });

        updateMetrics();
        syncSubscriptionUI();
        applyFilter();
    }

    /**
     * Handle live stock update
     */
    function handleStockUpdate(stock) {
        if (!stock || !stock.symbol) return;
        state.allTrackedSymbols.add(stock.symbol);
        updateStockCard(stock, true);
        updateGlobalLastUpdated(stock.timestamp);

        // If the updated stock is currently open in the detail modal, update it live!
        if (state.activeDetailSymbol === stock.symbol) {
            updateModalLiveStock(stock);
        }
    }

    /**
     * Handle subscription status acknowledgement
     */
    function handleSubscriptionStatus(msg) {
        console.log('Subscription acknowledgement:', msg.message);
        if (Array.isArray(msg.subscribed_symbols)) {
            state.subscribedSymbols = new Set(msg.subscribed_symbols);
            syncSubscriptionUI();
            updateMetrics();
        }
    }

    /**
     * Targeted update of an individual stock card without full re-render
     */
    function updateStockCard(stock, shouldAnimate) {
        const symbol = stock.symbol;
        const currentPrice = Number(stock.price);
        const prevRecordedPrice = state.lastPrices.has(symbol)
            ? state.lastPrices.get(symbol)
            : Number(stock.previous_price);

        state.lastPrices.set(symbol, currentPrice);

        let card = document.getElementById(`card-${symbol}`);
        if (!card) {
            card = createStockCardElement(stock);
            dom.stocksGrid.appendChild(card);
        }

        const priceEl = document.getElementById(`price-${symbol}`);
        const prevEl = document.getElementById(`prev-${symbol}`);
        const changeEl = document.getElementById(`change-${symbol}`);
        const percentEl = document.getElementById(`percent-${symbol}`);
        const arrowEl = document.getElementById(`arrow-${symbol}`);
        const movementWrap = document.getElementById(`movement-${symbol}`);
        const subPill = document.getElementById(`subPill-${symbol}`);

        if (priceEl) priceEl.textContent = formatCurrency(currentPrice);
        if (prevEl) prevEl.textContent = formatCurrency(stock.previous_price);
        if (changeEl) changeEl.textContent = formatSigned(stock.change);
        if (percentEl) percentEl.textContent = `(${formatSigned(stock.change_percent)}%)`;

        if (movementWrap && arrowEl) {
            movementWrap.classList.remove('gain', 'loss', 'neutral');
            if (stock.change > 0) {
                movementWrap.classList.add('gain');
                arrowEl.innerHTML = '&#9650;';
            } else if (stock.change < 0) {
                movementWrap.classList.add('loss');
                arrowEl.innerHTML = '&#9660;';
            } else {
                movementWrap.classList.add('neutral');
                arrowEl.innerHTML = '&bull;';
            }
        }

        const isSubscribed = state.subscribedSymbols.has(symbol);
        card.classList.toggle('unsubscribed', !isSubscribed);
        if (subPill) {
            subPill.className = `sub-status-pill ${isSubscribed ? 'subscribed' : 'paused'}`;
            subPill.textContent = isSubscribed ? 'LIVE' : 'PAUSED';
        }

        if (shouldAnimate) {
            card.classList.remove('flash-up', 'flash-down');
            void card.offsetWidth;

            if (currentPrice > prevRecordedPrice) {
                card.classList.add('flash-up');
            } else if (currentPrice < prevRecordedPrice) {
                card.classList.add('flash-down');
            }

            setTimeout(function () {
                card.classList.remove('flash-up', 'flash-down');
            }, 800);
        }
    }

    /**
     * Create a new stock card element dynamically if not present in initial DOM
     */
    function createStockCardElement(stock) {
        const card = document.createElement('article');
        card.className = 'stock-card';
        card.id = `card-${stock.symbol}`;
        card.dataset.symbol = stock.symbol;
        card.dataset.company = stock.company;
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `View live chart and full details for ${stock.symbol}`);
        card.setAttribute('title', 'Click to view interactive chart and full market details');

        card.innerHTML = `
            <div class="card-header">
                <div class="symbol-info">
                    <span class="stock-symbol font-mono">${stock.symbol}</span>
                    <span class="company-name" title="${stock.company}">${stock.company}</span>
                </div>
                <span class="sub-status-pill subscribed" id="subPill-${stock.symbol}">LIVE</span>
            </div>
            <div class="card-body">
                <div class="price-container">
                    <span class="currency-symbol">$</span>
                    <span class="current-price font-mono" id="price-${stock.symbol}">${formatCurrency(stock.price)}</span>
                </div>
                <div class="movement-container neutral" id="movement-${stock.symbol}">
                    <span class="direction-indicator" id="arrow-${stock.symbol}">&bull;</span>
                    <span class="price-change font-mono" id="change-${stock.symbol}">${formatSigned(stock.change)}</span>
                    <span class="percent-change font-mono" id="percent-${stock.symbol}">(${formatSigned(stock.change_percent)}%)</span>
                </div>
            </div>
            <div class="card-footer">
                <span class="prev-price-label">Prev: $<span id="prev-${stock.symbol}">${formatCurrency(stock.previous_price)}</span></span>
                <span class="card-action-hint">Chart &amp; Details &rarr;</span>
            </div>
        `;
        return card;
    }

    /**
     * Update global metrics bar
     */
    function updateMetrics() {
        if (dom.trackedCount) dom.trackedCount.textContent = state.allTrackedSymbols.size;
        if (dom.subCount) dom.subCount.textContent = state.subscribedSymbols.size;
    }

    /**
     * Update global last updated time
     */
    function updateGlobalLastUpdated(isoString) {
        if (!dom.lastUpdated) return;
        const now = isoString ? new Date(isoString) : new Date();
        dom.lastUpdated.textContent = now.toLocaleTimeString();
    }

    /**
     * Synchronize chip states and card subscription pills
     */
    function syncSubscriptionUI() {
        const chips = dom.chipsContainer ? dom.chipsContainer.querySelectorAll('.chip') : [];
        chips.forEach(function (chip) {
            const sym = chip.dataset.symbol;
            const isActive = state.subscribedSymbols.has(sym);
            chip.classList.toggle('active', isActive);
            chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });

        state.allTrackedSymbols.forEach(function (sym) {
            const card = document.getElementById(`card-${sym}`);
            const pill = document.getElementById(`subPill-${sym}`);
            const isSub = state.subscribedSymbols.has(sym);
            if (card) card.classList.toggle('unsubscribed', !isSub);
            if (pill) {
                pill.className = `sub-status-pill ${isSub ? 'subscribed' : 'paused'}`;
                pill.textContent = isSub ? 'LIVE' : 'PAUSED';
            }
        });
    }

    /**
     * Send subscription update message over WebSocket
     */
    function sendSubscriptionUpdate(symbols) {
        if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
            console.warn('Cannot send subscription: WebSocket is not open.');
            return;
        }

        const payload = {
            action: 'set',
            symbols: symbols,
        };

        try {
            state.ws.send(JSON.stringify(payload));
        } catch (e) {
            console.error('Failed to send subscription update:', e);
        }
    }

    /**
     * Toggle subscription for a specific symbol
     */
    function toggleSymbolSubscription(symbol) {
        if (state.subscribedSymbols.has(symbol)) {
            state.subscribedSymbols.delete(symbol);
        } else {
            state.subscribedSymbols.add(symbol);
        }
        sendSubscriptionUpdate(Array.from(state.subscribedSymbols));
        syncSubscriptionUI();
        updateMetrics();
    }

    /**
     * Filter displayed stocks based on search query without altering subscriptions
     */
    function applyFilter() {
        const query = state.searchQuery.trim().toLowerCase();
        const cards = dom.stocksGrid.querySelectorAll('.stock-card');
        let visibleCount = 0;

        cards.forEach(function (card) {
            const symbol = (card.dataset.symbol || '').toLowerCase();
            const company = (card.dataset.company || '').toLowerCase();
            const matches = !query || symbol.includes(query) || company.includes(query);

            card.classList.toggle('hidden', !matches);
            if (matches) visibleCount++;
        });

        if (visibleCount === 0 && cards.length > 0) {
            dom.emptyState.classList.remove('hidden');
            dom.emptyQueryText.textContent = state.searchQuery;
        } else {
            dom.emptyState.classList.add('hidden');
        }

        if (dom.filteredResultsLabel) {
            if (query) {
                dom.filteredResultsLabel.textContent = `Showing ${visibleCount} of ${cards.length} stocks`;
            } else {
                dom.filteredResultsLabel.textContent = `Showing all ${cards.length} stocks`;
            }
        }
    }

    /* ==========================================================================
       STOCK DETAILS MODAL & INTERACTIVE CHARTING ENGINE
       ========================================================================== */

    /**
     * Fetch full stock details from REST endpoint and display interactive modal
     */
    async function openStockDetail(symbol) {
        state.activeDetailSymbol = symbol;
        state.hoveredCandleIndex = null;
        state.crosshairPos = null;

        try {
            const res = await fetch(`/api/stocks/${symbol}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load stock details`);
            const data = await res.json();
            state.activeDetailData = data;
            state.activeCandles = Array.isArray(data.candles) ? data.candles.map(c => ({ ...c })) : [];

            populateModalData(data);
            if (dom.stockModal && typeof dom.stockModal.showModal === 'function') {
                dom.stockModal.showModal();
            } else if (dom.stockModal) {
                dom.stockModal.setAttribute('open', '');
            }

            // Sync user toggle buttons
            updateChartModeButtons();

            // Render chart after modal layout renders
            requestAnimationFrame(() => {
                renderStockChart();
            });
        } catch (err) {
            console.error('Error fetching stock details:', err);
        }
    }

    /**
     * Close stock detail dialog
     */
    function closeStockDetail() {
        state.activeDetailSymbol = null;
        state.activeDetailData = null;
        state.hoveredCandleIndex = null;
        state.crosshairPos = null;

        if (dom.stockModal) {
            if (typeof dom.stockModal.close === 'function') {
                dom.stockModal.close();
            } else {
                dom.stockModal.removeAttribute('open');
            }
        }
    }

    /**
     * Populate modal with complete corporate profile, fundamentals, and prices
     */
    function populateModalData(data) {
        if (!data) return;

        if (dom.modalStockSymbol) dom.modalStockSymbol.textContent = data.symbol;
        if (dom.modalCompanyName) dom.modalCompanyName.textContent = data.company;
        if (dom.modalSectorPill) dom.modalSectorPill.textContent = data.sector || 'Technology';
        if (dom.modalAboutName) dom.modalAboutName.textContent = data.company;
        if (dom.modalCompanyDesc) dom.modalCompanyDesc.textContent = data.description || '';

        if (dom.modalCurrentPrice) dom.modalCurrentPrice.textContent = formatCurrency(data.price);
        if (dom.modalChange) dom.modalChange.textContent = formatSigned(data.change);
        if (dom.modalChangePercent) dom.modalChangePercent.textContent = `(${formatSigned(data.change_percent)}%)`;

        if (dom.modalMovement && dom.modalArrow) {
            dom.modalMovement.classList.remove('gain', 'loss');
            if (data.change >= 0) {
                dom.modalMovement.classList.add('gain');
                dom.modalArrow.innerHTML = '&#9650;';
            } else {
                dom.modalMovement.classList.add('loss');
                dom.modalArrow.innerHTML = '&#9660;';
            }
        }

        if (dom.modalDayLow) dom.modalDayLow.textContent = formatCurrency(data.day_low || data.price * 0.99);
        if (dom.modalDayHigh) dom.modalDayHigh.textContent = formatCurrency(data.day_high || data.price * 1.01);
        if (dom.modalDayOpen) dom.modalDayOpen.textContent = formatCurrency(data.day_open || data.previous_price);
        if (dom.modalVolume) dom.modalVolume.textContent = formatVolume(data.volume || 10000000);
        if (dom.modalMarketCap) dom.modalMarketCap.textContent = data.market_cap || 'N/A';
        if (dom.modalPeRatio) dom.modalPeRatio.textContent = data.pe_ratio ? data.pe_ratio.toFixed(1) : 'N/A';
        if (dom.modal52Low) dom.modal52Low.textContent = formatCurrency(data.fifty_two_week_low || data.price * 0.85);
        if (dom.modal52High) dom.modal52High.textContent = formatCurrency(data.fifty_two_week_high || data.price * 1.25);

        // Update initial HUD values with latest candle
        if (state.activeCandles.length > 0) {
            updateChartHudWithCandle(state.activeCandles[state.activeCandles.length - 1]);
        }
    }

    /**
     * Update active detail modal when a live WebSocket tick arrives for it
     */
    function updateModalLiveStock(stock) {
        if (!state.activeDetailData) return;

        const newPrice = Number(stock.price);
        state.activeDetailData.price = newPrice;
        state.activeDetailData.change = stock.change;
        state.activeDetailData.change_percent = stock.change_percent;

        if (dom.modalCurrentPrice) dom.modalCurrentPrice.textContent = formatCurrency(newPrice);
        if (dom.modalChange) dom.modalChange.textContent = formatSigned(stock.change);
        if (dom.modalChangePercent) dom.modalChangePercent.textContent = `(${formatSigned(stock.change_percent)}%)`;

        if (dom.modalMovement && dom.modalArrow) {
            dom.modalMovement.classList.remove('gain', 'loss');
            if (stock.change >= 0) {
                dom.modalMovement.classList.add('gain');
                dom.modalArrow.innerHTML = '&#9650;';
            } else {
                dom.modalMovement.classList.add('loss');
                dom.modalArrow.innerHTML = '&#9660;';
            }
        }

        // Update day high / low
        if (newPrice > state.activeDetailData.day_high) {
            state.activeDetailData.day_high = newPrice;
            if (dom.modalDayHigh) dom.modalDayHigh.textContent = formatCurrency(newPrice);
        }
        if (newPrice < state.activeDetailData.day_low) {
            state.activeDetailData.day_low = newPrice;
            if (dom.modalDayLow) dom.modalDayLow.textContent = formatCurrency(newPrice);
        }

        // Mutate the active/current candle on the chart
        if (state.activeCandles.length > 0) {
            const currentCandle = state.activeCandles[state.activeCandles.length - 1];
            currentCandle.close = newPrice;
            currentCandle.high = Math.max(currentCandle.high, newPrice);
            currentCandle.low = Math.min(currentCandle.low, newPrice);
            currentCandle.volume += Math.floor(Math.random() * 2000 + 500);

            // Re-render chart with new candle coordinates
            renderStockChart();
            if (state.hoveredCandleIndex === null) {
                updateChartHudWithCandle(currentCandle);
            }
        }
    }

    /**
     * Switch chart mode between 'candles' and 'graph'
     */
    function setChartMode(mode) {
        state.chartMode = mode;
        localStorage.setItem('photon_chart_mode', mode);
        updateChartModeButtons();
        renderStockChart();
    }

    /**
     * Synchronize toggle button active states
     */
    function updateChartModeButtons() {
        const isCandles = state.chartMode === 'candles';
        if (dom.chartModeCandles) {
            dom.chartModeCandles.classList.toggle('active', isCandles);
            dom.chartModeCandles.setAttribute('aria-checked', isCandles ? 'true' : 'false');
        }
        if (dom.chartModeGraph) {
            dom.chartModeGraph.classList.toggle('active', !isCandles);
            dom.chartModeGraph.setAttribute('aria-checked', !isCandles ? 'true' : 'false');
        }
    }

    /**
     * Update Chart HUD elements
     */
    function updateChartHudWithCandle(candle) {
        if (!candle) return;
        if (dom.hudOpen) dom.hudOpen.textContent = formatCurrency(candle.open);
        if (dom.hudHigh) dom.hudHigh.textContent = formatCurrency(candle.high);
        if (dom.hudLow) dom.hudLow.textContent = formatCurrency(candle.low);
        if (dom.hudClose) dom.hudClose.textContent = formatCurrency(candle.close);
        if (dom.hudVol) dom.hudVol.textContent = formatVolume(candle.volume);

        if (dom.hudBadge) {
            dom.hudBadge.classList.remove('gain', 'loss', 'neutral');
            if (candle.close > candle.open) {
                dom.hudBadge.classList.add('gain');
                dom.hudBadge.textContent = 'BULLISH';
            } else if (candle.close < candle.open) {
                dom.hudBadge.classList.add('loss');
                dom.hudBadge.textContent = 'BEARISH';
            } else {
                dom.hudBadge.classList.add('neutral');
                dom.hudBadge.textContent = 'NEUTRAL';
            }
        }
    }

    /**
     * Render the high-definition canvas chart (Japanese Candlesticks or Area Line Graph)
     */
    function renderStockChart() {
        const canvas = dom.stockCanvas;
        if (!canvas) return;

        const container = dom.chartViewport;
        const rect = container.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return;

        const dpr = window.devicePixelRatio || 1;
        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;

        const ctx = canvas.getContext('2d');
        ctx.resetTransform();
        ctx.scale(dpr, dpr);

        const width = rect.width;
        const height = rect.height;

        // Margins for axes
        const padTop = 48;
        const padBottom = 36;
        const padLeft = 16;
        const padRight = 76;

        const plotWidth = width - padLeft - padRight;
        const plotHeight = height - padTop - padBottom;

        // Clear canvas background
        ctx.fillStyle = '#090e1a';
        ctx.fillRect(0, 0, width, height);

        const candles = state.activeCandles;
        if (!candles || candles.length === 0) {
            ctx.fillStyle = '#6b7280';
            ctx.font = '14px Plus Jakarta Sans, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No market candle data available', width / 2, height / 2);
            return;
        }

        // Determine price bounds
        let minPrice = Infinity;
        let maxPrice = -Infinity;
        candles.forEach(c => {
            if (c.low < minPrice) minPrice = c.low;
            if (c.high > maxPrice) maxPrice = c.high;
        });

        const buffer = (maxPrice - minPrice) * 0.08 || 0.5;
        minPrice = Math.max(0.01, minPrice - buffer);
        maxPrice = maxPrice + buffer;
        const priceRange = maxPrice - minPrice;

        function priceToY(p) {
            return padTop + plotHeight - ((p - minPrice) / priceRange) * plotHeight;
        }

        function yToPrice(y) {
            return minPrice + ((padTop + plotHeight - y) / plotHeight) * priceRange;
        }

        // Draw horizontal gridlines & price labels
        const gridSteps = 6;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
        ctx.lineWidth = 1;
        ctx.font = '12px JetBrains Mono, monospace';
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        for (let i = 0; i <= gridSteps; i++) {
            const gridPrice = minPrice + (priceRange / gridSteps) * i;
            const y = priceToY(gridPrice);

            ctx.beginPath();
            ctx.moveTo(padLeft, y);
            ctx.lineTo(width - padRight, y);
            ctx.stroke();

            // Price label on right axis
            ctx.fillStyle = '#64748b';
            ctx.fillText(gridPrice.toFixed(2), width - padRight + 8, y);
        }

        // Candle slot width
        const count = candles.length;
        const slotWidth = plotWidth / count;
        const candleBodyWidth = Math.max(3, Math.min(slotWidth * 0.72, 28));

        // Draw time labels along bottom axis
        const timeLabelInterval = Math.max(1, Math.floor(count / 6));
        ctx.fillStyle = '#64748b';
        ctx.font = '12px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        for (let i = 0; i < count; i += timeLabelInterval) {
            const x = padLeft + i * slotWidth + slotWidth / 2;
            const timeStr = candles[i].time || '';
            ctx.fillText(timeStr, x, height - padBottom + 8);
        }

        // Render Mode 1: Japanese Candlesticks
        if (state.chartMode === 'candles') {
            candles.forEach((c, i) => {
                const xCenter = padLeft + i * slotWidth + slotWidth / 2;
                const isBullish = c.close >= c.open;
                const color = isBullish ? '#10b981' : '#ef4444';

                const yHigh = priceToY(c.high);
                const yLow = priceToY(c.low);
                const yOpen = priceToY(c.open);
                const yClose = priceToY(c.close);

                // Draw Wick
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(xCenter, yHigh);
                ctx.lineTo(xCenter, yLow);
                ctx.stroke();

                // Draw Body
                const bodyTop = Math.min(yOpen, yClose);
                const bodyHeight = Math.max(2, Math.abs(yClose - yOpen));

                ctx.fillStyle = color;
                ctx.fillRect(xCenter - candleBodyWidth / 2, bodyTop, candleBodyWidth, bodyHeight);
            });
        } 
        // Render Mode 2: Continuous Area & Line Graph
        else {
            const linePoints = [];
            candles.forEach((c, i) => {
                const x = padLeft + i * slotWidth + slotWidth / 2;
                const y = priceToY(c.close);
                linePoints.push({ x, y, price: c.close });
            });

            const isOverallPositive = candles[candles.length - 1].close >= candles[0].open;
            const lineColor = isOverallPositive ? '#10b981' : '#ef4444';
            const gradientTopColor = isOverallPositive ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)';

            // Draw Area Fill Gradient
            const gradient = ctx.createLinearGradient(0, padTop, 0, padTop + plotHeight);
            gradient.addColorStop(0, gradientTopColor);
            gradient.addColorStop(1, 'rgba(9, 14, 26, 0.0)');

            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.moveTo(linePoints[0].x, padTop + plotHeight);
            linePoints.forEach(pt => ctx.lineTo(pt.x, pt.y));
            ctx.lineTo(linePoints[linePoints.length - 1].x, padTop + plotHeight);
            ctx.closePath();
            ctx.fill();

            // Draw Line
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            linePoints.forEach((pt, idx) => {
                if (idx === 0) ctx.moveTo(pt.x, pt.y);
                else ctx.lineTo(pt.x, pt.y);
            });
            ctx.stroke();

            // Glowing Pulsing Dot at latest point
            const lastPt = linePoints[linePoints.length - 1];
            ctx.fillStyle = lineColor;
            ctx.beginPath();
            ctx.arc(lastPt.x, lastPt.y, 4, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(lastPt.x, lastPt.y, 7, 0, Math.PI * 2);
            ctx.stroke();
        }

        // Draw Interactive Crosshair & Tooltip if user is hovering
        if (state.crosshairPos && state.hoveredCandleIndex !== null && candles[state.hoveredCandleIndex]) {
            const hoveredCandle = candles[state.hoveredCandleIndex];
            const hoveredX = padLeft + state.hoveredCandleIndex * slotWidth + slotWidth / 2;
            const hoveredY = Math.max(padTop, Math.min(height - padBottom, state.crosshairPos.y));

            // Dashed Crosshair Lines
            ctx.save();
            ctx.setLineDash([4, 4]);
            ctx.strokeStyle = 'rgba(148, 163, 184, 0.6)';
            ctx.lineWidth = 1;

            // Vertical line
            ctx.beginPath();
            ctx.moveTo(hoveredX, padTop);
            ctx.lineTo(hoveredX, height - padBottom);
            ctx.stroke();

            // Horizontal line
            ctx.beginPath();
            ctx.moveTo(padLeft, hoveredY);
            ctx.lineTo(width - padRight, hoveredY);
            ctx.stroke();
            ctx.restore();

            // Right price badge
            const crosshairPrice = yToPrice(hoveredY);
            ctx.fillStyle = '#3b82f6';
            ctx.fillRect(width - padRight + 2, hoveredY - 11, padRight - 6, 22);
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 12px JetBrains Mono, monospace';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillText(crosshairPrice.toFixed(2), width - padRight + 6, hoveredY);

            // Bottom time badge
            const timeText = hoveredCandle.time || '';
            const textWidth = ctx.measureText(timeText).width;
            ctx.fillStyle = '#1e293b';
            ctx.fillRect(hoveredX - textWidth / 2 - 8, height - padBottom + 2, textWidth + 16, 20);
            ctx.fillStyle = '#94a3b8';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(timeText, hoveredX, height - padBottom + 12);
        }
    }

    /**
     * Handle mouse move over chart canvas
     */
    function handleCanvasMouseMove(e) {
        const canvas = dom.stockCanvas;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const padLeft = 16;
        const padRight = 76;
        const plotWidth = rect.width - padLeft - padRight;
        const count = state.activeCandles.length;
        if (count === 0) return;

        const slotWidth = plotWidth / count;
        const relX = mouseX - padLeft;

        if (relX >= 0 && relX <= plotWidth && mouseY >= 0 && mouseY <= rect.height) {
            const index = Math.min(count - 1, Math.max(0, Math.floor(relX / slotWidth)));
            state.hoveredCandleIndex = index;
            state.crosshairPos = { x: mouseX, y: mouseY };

            const hoveredCandle = state.activeCandles[index];
            updateChartHudWithCandle(hoveredCandle);
            renderStockChart();
        } else {
            handleCanvasMouseLeave();
        }
    }

    /**
     * Handle mouse leaving canvas
     */
    function handleCanvasMouseLeave() {
        state.hoveredCandleIndex = null;
        state.crosshairPos = null;
        if (state.activeCandles.length > 0) {
            updateChartHudWithCandle(state.activeCandles[state.activeCandles.length - 1]);
        }
        renderStockChart();
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        // Search Input
        dom.stockSearchInput.addEventListener('input', function (e) {
            state.searchQuery = e.target.value;
            dom.clearSearchBtn.classList.toggle('hidden', !state.searchQuery);
            applyFilter();
        });

        // Clear Search Button
        dom.clearSearchBtn.addEventListener('click', function () {
            state.searchQuery = '';
            dom.stockSearchInput.value = '';
            dom.clearSearchBtn.classList.add('hidden');
            dom.stockSearchInput.focus();
            applyFilter();
        });

        // Reset Search Button in Empty State
        dom.resetSearchBtn.addEventListener('click', function () {
            state.searchQuery = '';
            dom.stockSearchInput.value = '';
            dom.clearSearchBtn.classList.add('hidden');
            applyFilter();
        });

        // Select All Subscriptions
        dom.selectAllBtn.addEventListener('click', function () {
            state.subscribedSymbols = new Set(state.allTrackedSymbols);
            sendSubscriptionUpdate(Array.from(state.subscribedSymbols));
            syncSubscriptionUI();
            updateMetrics();
        });

        // Deselect All Subscriptions
        dom.deselectAllBtn.addEventListener('click', function () {
            state.subscribedSymbols.clear();
            sendSubscriptionUpdate([]);
            syncSubscriptionUI();
            updateMetrics();
        });

        // Chip Clicks
        dom.chipsContainer.addEventListener('click', function (e) {
            const chip = e.target.closest('.chip');
            if (chip && chip.dataset.symbol) {
                toggleSymbolSubscription(chip.dataset.symbol);
            }
        });

        // Manual Reconnect Button
        dom.manualReconnectBtn.addEventListener('click', function () {
            state.reconnectAttempts = 0;
            initWebSocket();
        });

        // Click Stock Card to Open Modal
        dom.stocksGrid.addEventListener('click', function (e) {
            const card = e.target.closest('.stock-card');
            if (card && card.dataset.symbol) {
                openStockDetail(card.dataset.symbol);
            }
        });

        // Keyboard navigation to open stock modal on Enter / Space
        dom.stocksGrid.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                const card = e.target.closest('.stock-card');
                if (card && card.dataset.symbol) {
                    e.preventDefault();
                    openStockDetail(card.dataset.symbol);
                }
            }
        });

        // Close Modal Button
        if (dom.closeModalBtn) {
            dom.closeModalBtn.addEventListener('click', closeStockDetail);
        }

        // Close on backdrop click
        if (dom.stockModal) {
            dom.stockModal.addEventListener('click', function (e) {
                const rect = dom.stockModal.getBoundingClientRect();
                const isInDialog = (
                    rect.top <= e.clientY &&
                    e.clientY <= rect.top + rect.height &&
                    rect.left <= e.clientX &&
                    e.clientX <= rect.left + rect.width
                );
                if (!isInDialog) {
                    closeStockDetail();
                }
            });

            dom.stockModal.addEventListener('cancel', function () {
                closeStockDetail();
            });
        }

        // Chart Mode Switchers
        if (dom.chartModeCandles) {
            dom.chartModeCandles.addEventListener('click', function () {
                setChartMode('candles');
            });
        }

        if (dom.chartModeGraph) {
            dom.chartModeGraph.addEventListener('click', function () {
                setChartMode('graph');
            });
        }

        // Canvas hover interactions
        if (dom.stockCanvas) {
            dom.stockCanvas.addEventListener('mousemove', handleCanvasMouseMove);
            dom.stockCanvas.addEventListener('mouseleave', handleCanvasMouseLeave);
        }

        // Redraw on window resize
        window.addEventListener('resize', function () {
            if (state.activeDetailSymbol) {
                renderStockChart();
            }
        });
    }

    /**
     * Initialize on DOM ready
     */
    document.addEventListener('DOMContentLoaded', function () {
        const existingCards = dom.stocksGrid.querySelectorAll('.stock-card');
        existingCards.forEach(function (card) {
            const sym = card.dataset.symbol;
            if (sym) {
                state.allTrackedSymbols.add(sym);
                state.subscribedSymbols.add(sym);
                const priceEl = document.getElementById(`price-${sym}`);
                if (priceEl) {
                    const parsed = parseFloat(priceEl.textContent.replace(/[^0-9.]/g, ''));
                    if (!isNaN(parsed)) state.lastPrices.set(sym, parsed);
                }
            }
        });

        setupEventListeners();
        updateMetrics();
        initWebSocket();
    });

})();
