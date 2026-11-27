import React, { useEffect, useRef, useState, useCallback } from 'react';
import { init, dispose } from 'klinecharts';
import {
  TrendingUp,
  ArrowUpRight,
  Minus,
  Trash2,
  Eye,
  EyeOff,
  Smartphone,
  X,
} from 'lucide-react';
import { api } from '../api/client';

const TIMEFRAMES = [
  { id: '1m', label: '1m', period: { span: 1, type: 'minute' } },
  { id: '5m', label: '5m', period: { span: 5, type: 'minute' } },
  { id: '15m', label: '15m', period: { span: 15, type: 'minute' } },
  { id: '30m', label: '30m', period: { span: 30, type: 'minute' } },
  { id: '1h', label: '1H', period: { span: 1, type: 'hour' } },
  { id: '4h', label: '4H', period: { span: 4, type: 'hour' } },
  { id: '1d', label: '1D', period: { span: 1, type: 'day' } },
];

const DRAWING_TOOLS = [
  { id: 'segment', label: 'Trendline', Icon: TrendingUp },
  { id: 'rayLine', label: 'Ray', Icon: ArrowUpRight },
  { id: 'horizontalStraightLine', label: 'Horizontal', Icon: Minus },
];

const SHAPE_COLORS = [
  '#3b82f6',
  '#10b981',
  '#f43f5e',
  '#f59e0b',
  '#a855f7',
  '#e2e8f0',
];

const INDICATORS = [
  { id: 'EMA', label: 'EMA', isOverlay: true },
  { id: 'BOLL', label: 'BOLL', isOverlay: true },
  { id: 'VOL', label: 'VOL', isOverlay: false },
  { id: 'RSI', label: 'RSI', isOverlay: false },
  { id: 'MACD', label: 'MACD', isOverlay: false },
];

const DRAWINGS_STORAGE_PREFIX = 'superchart_drawings_v1_';
const INDICATORS_STORAGE_KEY = 'superchart_indicators_v1';
const LEGEND_STORAGE_KEY = 'superchart_legend_visible_v1';

const safeReadJson = (key, fallback) => {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (e) {
    return fallback;
  }
};

const safeWriteJson = (key, val) => {
  try {
    window.localStorage.setItem(key, JSON.stringify(val));
  } catch (e) {
    // Ignore restricted WebView localStorage failures
  }
};

const inferPrecision = (bars) => {
  if (!bars || bars.length === 0) return 2;
  const sample = bars[bars.length - 1]?.close ?? 1;
  if (sample < 0.001) return 8;
  if (sample < 0.1) return 6;
  if (sample < 10) return 4;
  return 2;
};

const buildChartStyles = (showLegend) => ({
  grid: {
    show: true,
    horizontal: { color: '#1e293b', style: 'dashed' },
    vertical: { color: '#1e293b', style: 'dashed' },
  },
  candle: {
    bar: {
      upColor: '#10b981',
      downColor: '#f43f5e',
      upBorderColor: '#10b981',
      downBorderColor: '#f43f5e',
      upWickColor: '#10b981',
      downWickColor: '#f43f5e',
    },
    priceMark: {
      last: {
        show: true,
        upColor: '#10b981',
        downColor: '#f43f5e',
      },
    },
    tooltip: {
      showRule: showLegend ? 'always' : 'none',
      showType: 'standard',
      offsetTop: 2,
      offsetLeft: 6,
      title: {
        show: false,
        size: 10,
      },
      legend: {
        size: 10,
        color: '#94a3b8',
        defaultValue: '—',
        marginLeft: 6,
        marginRight: 4,
        marginTop: 2,
        marginBottom: 2,
        template: ({ current }) => {
          if (!current) return [];
          const isUp = current.close >= current.open;
          const valColor = isUp ? '#10b981' : '#f43f5e';
          return [
            { title: { text: 'O:', color: '#64748b' }, value: { text: String(current.open), color: valColor } },
            { title: { text: 'H:', color: '#64748b' }, value: { text: String(current.high), color: valColor } },
            { title: { text: 'L:', color: '#64748b' }, value: { text: String(current.low), color: valColor } },
            { title: { text: 'C:', color: '#64748b' }, value: { text: String(current.close), color: valColor } },
          ];
        },
      },
    },
  },
  indicator: {
    tooltip: {
      showRule: showLegend ? 'always' : 'none',
      title: {
        show: showLegend,
        size: 10,
        color: '#94a3b8',
      },
      legend: {
        size: 10,
        color: '#94a3b8',
      },
    },
  },
  xAxis: {
    axisLine: { color: '#334155' },
    tickText: { color: '#94a3b8', size: 10 },
  },
  yAxis: {
    axisLine: { color: '#334155' },
    tickText: { color: '#94a3b8', size: 10 },
  },
  crosshair: {
    horizontal: { line: { color: '#64748b' } },
    vertical: { line: { color: '#64748b' } },
  },
});

const mapRotatedTouch = (touch, box, target) => {
  const clientX = box.left + (touch.clientY - box.top);
  const clientY = box.top + (box.right - touch.clientX);
  const pageX = clientX + window.scrollX;
  const pageY = clientY + window.scrollY;

  return new Touch({
    identifier: touch.identifier,
    target,
    clientX,
    clientY,
    pageX,
    pageY,
    screenX: clientX,
    screenY: clientY,
    radiusX: touch.radiusX || 1,
    radiusY: touch.radiusY || 1,
    rotationAngle: touch.rotationAngle || 0,
    force: touch.force || 1,
  });
};

const SuperchartView = ({ pairs = [], initialSymbol = 'BTCUSDT', onOpenVipModal }) => {
  const wrapperRef = useRef(null);
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const wsRef = useRef(null);
  const isRestoringRef = useRef(false);
  const mountedRef = useRef(true);

  const [symbol, setSymbol] = useState(initialSymbol || 'BTCUSDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [activeTool, setActiveTool] = useState(null);
  const [selectedOverlay, setSelectedOverlay] = useState(null); // { id, color }
  const [activeIndicators, setActiveIndicators] = useState(() => {
    const saved = safeReadJson(INDICATORS_STORAGE_KEY, ['VOL']);
    return Array.isArray(saved) ? saved : ['VOL'];
  });
  const [showLegend, setShowLegend] = useState(() => {
    const saved = safeReadJson(LEGEND_STORAGE_KEY, true);
    return typeof saved === 'boolean' ? saved : true;
  });
  const [isLandscape, setIsLandscape] = useState(false);
  const [isCssRotated, setIsCssRotated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [errorBanner, setErrorBanner] = useState(null);
  const [retryNonce, setRetryNonce] = useState(0);

  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;

  const persistDrawingsForCurrentSymbol = useCallback(() => {
    const chart = chartRef.current;
    if (!chart || isRestoringRef.current) return;
    const overlays = chart.getOverlays() || [];
    const serialized = overlays
      .filter((ov) => Array.isArray(ov.points) && ov.points.length > 0)
      .map((ov) => ({
        name: ov.name,
        color: ov.styles?.line?.color || '#3b82f6',
        points: ov.points.map((pt) => ({
          timestamp: pt.timestamp,
          dataIndex: pt.dataIndex,
          value: pt.value,
        })),
      }));
    safeWriteJson(`${DRAWINGS_STORAGE_PREFIX}${symbolRef.current}`, serialized);
  }, []);

  const attachOverlayLifecycle = useCallback(
    (overlayConfig) => ({
      ...overlayConfig,
      onDrawEnd: () => {
        setActiveTool(null);
        persistDrawingsForCurrentSymbol();
      },
      onPressedMoveEnd: () => persistDrawingsForCurrentSymbol(),
      onRemoved: ({ overlay }) => {
        setSelectedOverlay((prev) => (prev?.id === overlay?.id ? null : prev));
        persistDrawingsForCurrentSymbol();
      },
      onSelected: ({ overlay }) => {
        if (!overlay) return;
        setSelectedOverlay({
          id: overlay.id,
          color: overlay.styles?.line?.color || '#3b82f6',
        });
      },
      onDeselected: ({ overlay }) => {
        setSelectedOverlay((prev) => (prev?.id === overlay?.id ? null : prev));
      },
    }),
    [persistDrawingsForCurrentSymbol]
  );

  const restoreDrawingsForSymbol = useCallback(
    (sym) => {
      const chart = chartRef.current;
      if (!chart) return;
      isRestoringRef.current = true;
      try {
        chart.removeOverlay();
        setSelectedOverlay(null);
        const saved = safeReadJson(`${DRAWINGS_STORAGE_PREFIX}${sym}`, []);
        if (Array.isArray(saved) && saved.length > 0) {
          saved.forEach((item) => {
            if (!item?.name || !Array.isArray(item.points) || item.points.length === 0) return;
            const color = item.color || '#3b82f6';
            chart.createOverlay(
              attachOverlayLifecycle({
                name: item.name,
                points: item.points,
                styles: {
                  line: { color },
                  point: { borderColor: color, activeBorderColor: color },
                },
              })
            );
          });
        }
      } finally {
        isRestoringRef.current = false;
      }
    },
    [attachOverlayLifecycle]
  );

  // 1. Initialize klinecharts once and dispose strictly on unmount
  useEffect(() => {
    mountedRef.current = true;
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = init(container, {
      styles: buildChartStyles(showLegend),
    });
    chartRef.current = chart;

    const savedIndicators = safeReadJson(INDICATORS_STORAGE_KEY, ['VOL']);
    if (Array.isArray(savedIndicators)) {
      savedIndicators.forEach((indId) => {
        const meta = INDICATORS.find((i) => i.id === indId);
        if (!meta) return;
        if (meta.isOverlay) {
          chart.createIndicator({ name: meta.id, paneId: 'candle_pane' }, true);
        } else {
          chart.createIndicator(meta.id);
        }
      });
    }

    const handleResize = () => {
      chartRef.current?.resize();
    };

    let observer = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(handleResize);
      observer.observe(container);
    }
    window.addEventListener('resize', handleResize);

    return () => {
      mountedRef.current = false;
      window.removeEventListener('resize', handleResize);
      observer?.disconnect();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      dispose(container);
      chartRef.current = null;
    };
  }, []);

  // 2. Sync compact legend visibility toggle dynamically
  useEffect(() => {
    safeWriteJson(LEGEND_STORAGE_KEY, showLegend);
    chartRef.current?.setStyles(buildChartStyles(showLegend));
  }, [showLegend]);

  // 3. Resize chart when switching portrait/landscape
  useEffect(() => {
    const timer = window.setTimeout(() => {
      chartRef.current?.resize();
    }, 60);
    return () => window.clearTimeout(timer);
  }, [isLandscape, isCssRotated]);

  // 4. Phase 4 CRITICAL: Landscape Touch/Mouse Coordinate Transformer
  // Swaps & translates clientX/clientY back into unrotated canvas coordinates when CSS rotate(90deg) is active.
  useEffect(() => {
    if (!isCssRotated) return undefined;

    let activeTouchPane = null;

    const handleTouch = (e) => {
      if (e.__landscapeMapped) return;
      const container = containerRef.current;
      if (!container) return;

      if (e.type === 'touchstart' && container.contains(e.target)) {
        activeTouchPane = e.target;
      }

      const targetEl = activeTouchPane && container.contains(activeTouchPane) ? activeTouchPane : null;
      if (!targetEl) return;

      if (e.type === 'touchend' || e.type === 'touchcancel') {
        if (e.touches.length === 0) {
          activeTouchPane = null;
        }
      }

      // Check WebKit/Chromium Touch constructor availability
      if (typeof Touch === 'undefined' || typeof TouchEvent === 'undefined') return;

      try {
        const box = targetEl.getBoundingClientRect();
        const mapList = (list) => Array.from(list || []).map((t) => mapRotatedTouch(t, box, targetEl));

        e.stopImmediatePropagation();
        if (e.cancelable && e.type !== 'touchstart') {
          e.preventDefault();
        }

        const mappedEvent = new TouchEvent(e.type, {
          bubbles: true,
          cancelable: e.cancelable,
          composed: true,
          touches: mapList(e.touches),
          targetTouches: mapList(e.targetTouches),
          changedTouches: mapList(e.changedTouches),
        });
        mappedEvent.__landscapeMapped = true;
        targetEl.dispatchEvent(mappedEvent);
      } catch (err) {
        // Ignore if environment forbids synthetic TouchEvent construction
      }
    };

    const handleMouse = (e) => {
      if (e.__landscapeMapped) return;
      const container = containerRef.current;
      if (!container || !container.contains(e.target)) return;

      const box = e.target.getBoundingClientRect();
      const clientX = box.left + (e.clientY - box.top);
      const clientY = box.top + (box.right - e.clientX);

      e.stopImmediatePropagation();
      const mappedMouse = new MouseEvent(e.type, {
        bubbles: true,
        cancelable: e.cancelable,
        view: window,
        button: e.button,
        buttons: e.buttons,
        clientX,
        clientY,
      });
      mappedMouse.__landscapeMapped = true;
      e.target.dispatchEvent(mappedMouse);
    };

    const touchOpts = { capture: true, passive: false };
    document.addEventListener('touchstart', handleTouch, touchOpts);
    document.addEventListener('touchmove', handleTouch, touchOpts);
    document.addEventListener('touchend', handleTouch, touchOpts);
    document.addEventListener('touchcancel', handleTouch, touchOpts);
    document.addEventListener('mousedown', handleMouse, true);
    document.addEventListener('mousemove', handleMouse, true);
    document.addEventListener('mouseup', handleMouse, true);

    return () => {
      document.removeEventListener('touchstart', handleTouch, touchOpts);
      document.removeEventListener('touchmove', handleTouch, touchOpts);
      document.removeEventListener('touchend', handleTouch, touchOpts);
      document.removeEventListener('touchcancel', handleTouch, touchOpts);
      document.removeEventListener('mousedown', handleMouse, true);
      document.removeEventListener('mousemove', handleMouse, true);
      document.removeEventListener('mouseup', handleMouse, true);
    };
  }, [isCssRotated]);

  // 5. Phase 1: klinecharts v10 DataLoader (Initial Fetch + Infinite Left Scroll + WebSocket Live Updates)
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return undefined;

    let isEffectActive = true;
    let retryTimer = null;
    let attempt = 0;
    const activeControllers = new Set();

    const closeStream = () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };

    const tfMeta = TIMEFRAMES.find((t) => t.id === timeframe) || TIMEFRAMES[2];

    chart.setDataLoader({
      getBars: async ({ type, timestamp, callback }) => {
        if (!isEffectActive) {
          callback([], false);
          return;
        }

        const controller = new AbortController();
        activeControllers.add(controller);

        if (type === 'init') {
          setIsLoading(true);
        } else if (type === 'forward') {
          setIsLoadingMore(true);
        }

        try {
          const beforeTs = type === 'forward' && timestamp ? timestamp : null;
          const payload = await api.getMarketKlines(symbol, timeframe, 200, beforeTs, controller.signal);
          if (!isEffectActive || controller.signal.aborted) return;

          const bars = Array.isArray(payload?.bars) ? payload.bars : [];
          if (type === 'init' && bars.length === 0) {
            const emptyErr = new Error('داده‌ای از صرافی دریافت نشد.');
            emptyErr.status = 503;
            throw emptyErr;
          }

          setErrorBanner(null);
          if (type === 'init') {
            setIsLoading(false);
            const precision = inferPrecision(bars);
            // Update symbol precision smoothly on loaded dataset
            const currentSym = chart.getSymbol();
            if (currentSym && currentSym.pricePrecision !== precision) {
              currentSym.pricePrecision = precision;
            }
          } else if (type === 'forward') {
            setIsLoadingMore(false);
          }

          const hasMore = Boolean(payload?.hasMore && bars.length > 0);
          callback(bars, { forward: hasMore, backward: false });

          if (type === 'init') {
            restoreDrawingsForSymbol(symbol);
          }
        } catch (err) {
          if (!isEffectActive || controller.signal.aborted || err?.name === 'AbortError') return;

          if (type === 'forward') {
            setIsLoadingMore(false);
            callback([], { forward: true, backward: false });
            return;
          }

          setIsLoading(false);
          callback([], false);

          if (err?.status === 403) {
            setErrorBanner({
              message: err.message || 'اشتراک VIP فعال مورد نیاز است.',
              isVipError: true,
              attempt: 0,
            });
            return;
          }

          attempt += 1;
          const delayMs = Math.min(1500 * Math.pow(2, attempt - 1), 30000);
          setErrorBanner({
            message: 'Failed to fetch market data. Retrying...',
            faMessage: `خطا در دریافت اطلاعات بازار. تلاش مجدد تا ${Math.round(delayMs / 1000)} ثانیه دیگر...`,
            isVipError: false,
            attempt,
          });
          retryTimer = window.setTimeout(() => {
            if (isEffectActive) setRetryNonce((n) => n + 1);
          }, delayMs);
        } finally {
          activeControllers.delete(controller);
        }
      },

      subscribeBar: ({ callback }) => {
        closeStream();
        if (!isEffectActive) return;

        try {
          const ws = new WebSocket(api.getMarketStreamUrl(symbol, timeframe));
          wsRef.current = ws;

          ws.onmessage = (evt) => {
            if (!isEffectActive) return;
            try {
              const msg = JSON.parse(evt.data);
              if (msg?.type === 'kline' && msg.bar) {
                callback(msg.bar);
              }
            } catch (parseErr) {
              // Ignore malformed frames
            }
          };

          ws.onerror = () => {
            // Silently ignore transient WS errors; REST init already succeeded
          };
        } catch (wsErr) {
          // WebSocket unavailable in restricted environment
        }
      },

      unsubscribeBar: () => {
        closeStream();
      },
    });

    const initialPairMeta = pairs.find((p) => p.symbol === symbol);
    const initialNum = parseFloat(initialPairMeta?.defaultPrice || '100');
    const initialPrecision = Number.isFinite(initialNum)
      ? inferPrecision([{ close: initialNum }])
      : 2;

    chart.setSymbol({ ticker: symbol, pricePrecision: initialPrecision, volumePrecision: 2 });
    chart.setPeriod(tfMeta.period);

    return () => {
      isEffectActive = false;
      closeStream();
      if (retryTimer) window.clearTimeout(retryTimer);
      activeControllers.forEach((ctrl) => ctrl.abort());
      activeControllers.clear();
    };
  }, [symbol, timeframe, retryNonce, restoreDrawingsForSymbol]);

  const handleToggleLandscape = async () => {
    if (isLandscape) {
      try {
        window.screen?.orientation?.unlock?.();
      } catch (e) {
        // Ignore unsupported Orientation API
      }
      setIsLandscape(false);
      setIsCssRotated(false);
      return;
    }

    let nativeLocked = false;
    try {
      if (window.screen?.orientation?.lock) {
        await window.screen.orientation.lock('landscape');
        nativeLocked = window.innerWidth > window.innerHeight;
      }
    } catch (e) {
      nativeLocked = false;
    }

    setIsLandscape(true);
    setIsCssRotated(!nativeLocked);
  };

  const handleActivateDrawingTool = (toolId) => {
    const chart = chartRef.current;
    if (!chart) return;
    setActiveTool(toolId);
    chart.createOverlay(attachOverlayLifecycle({ name: toolId }));
  };

  const handleClearDrawings = () => {
    chartRef.current?.removeOverlay();
    setSelectedOverlay(null);
    safeWriteJson(`${DRAWINGS_STORAGE_PREFIX}${symbol}`, []);
    setActiveTool(null);
  };

  const handleChangeSelectedColor = (color) => {
    const chart = chartRef.current;
    if (!chart || !selectedOverlay) return;
    chart.overrideOverlay({
      id: selectedOverlay.id,
      styles: {
        line: { color },
        point: { borderColor: color, activeBorderColor: color },
      },
    });
    setSelectedOverlay((prev) => (prev ? { ...prev, color } : null));
    persistDrawingsForCurrentSymbol();
  };

  const handleDeleteSelectedOverlay = () => {
    const chart = chartRef.current;
    if (!chart || !selectedOverlay) return;
    chart.removeOverlay({ id: selectedOverlay.id });
    setSelectedOverlay(null);
    persistDrawingsForCurrentSymbol();
  };

  const handleToggleIndicator = (indMeta) => {
    const chart = chartRef.current;
    if (!chart) return;
    const isActive = activeIndicators.includes(indMeta.id);
    let next;
    if (isActive) {
      chart.removeIndicator({ name: indMeta.id });
      next = activeIndicators.filter((id) => id !== indMeta.id);
    } else {
      if (indMeta.isOverlay) {
        chart.createIndicator({ name: indMeta.id, paneId: 'candle_pane' }, true);
      } else {
        chart.createIndicator(indMeta.id);
      }
      next = [...activeIndicators, indMeta.id];
    }
    setActiveIndicators(next);
    safeWriteJson(INDICATORS_STORAGE_KEY, next);
  };

  const pairOptions =
    pairs.length > 0
      ? pairs
      : [{ symbol: 'BTCUSDT', label: 'BTC / USDT' }, { symbol: 'ETHUSDT', label: 'ETH / USDT' }];

  return (
    <div
      ref={wrapperRef}
      dir="rtl"
      className={
        isCssRotated
          ? 'fullscreen-landscape bg-[#0b0f19] flex flex-col overflow-hidden'
          : isLandscape
          ? 'fixed inset-0 z-[9999] bg-[#0b0f19] flex flex-col overflow-hidden'
          : 'flex-1 min-h-0 flex flex-col bg-[#0b0f19] overflow-hidden'
      }
    >
      {/* Top Toolbar: Symbol, Timeframes, Indicators, Legend Eye Toggle & Landscape Button */}
      <div className="shrink-0 px-2.5 py-1.5 bg-gray-950/95 border-b border-gray-800 flex flex-wrap items-center justify-between gap-1.5">
        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-gray-900 border border-gray-700 text-amber-300 font-mono text-[11px] font-bold rounded-lg px-2 py-1 focus:outline-none focus:border-amber-500"
          >
            {pairOptions.map((p) => (
              <option key={p.symbol} value={p.symbol}>
                {p.label || p.symbol}
              </option>
            ))}
          </select>

          <div dir="ltr" className="flex items-center gap-0.5 bg-gray-900 p-0.5 rounded-lg border border-gray-800 overflow-x-auto">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.id}
                type="button"
                onClick={() => setTimeframe(tf.id)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold transition-colors ${
                  timeframe === tf.id
                    ? 'bg-amber-500 text-gray-950'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>

          <div dir="ltr" className="flex items-center gap-1">
            {INDICATORS.map((ind) => {
              const on = activeIndicators.includes(ind.id);
              return (
                <button
                  key={ind.id}
                  type="button"
                  onClick={() => handleToggleIndicator(ind)}
                  className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold border transition-colors ${
                    on
                      ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                      : 'bg-gray-950 border-gray-800 text-gray-500 hover:text-gray-300'
                  }`}
                >
                  {ind.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={() => setShowLegend((v) => !v)}
            title={showLegend ? 'مخفی کردن اطلاعات OHLCV' : 'نمایش اطلاعات OHLCV'}
            className={`p-1.5 rounded-lg border transition-colors ${
              showLegend
                ? 'bg-gray-900 border-gray-700 text-gray-300 hover:text-white'
                : 'bg-gray-950 border-gray-800 text-gray-500 hover:text-gray-300'
            }`}
          >
            {showLegend ? <Eye size={14} /> : <EyeOff size={14} />}
          </button>

          <button
            type="button"
            onClick={handleToggleLandscape}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-gradient-to-r from-amber-500 to-yellow-400 hover:brightness-110 text-gray-950 text-[10px] sm:text-xs font-extrabold shadow shadow-amber-500/20"
          >
            {isLandscape ? <X size={13} /> : <Smartphone size={13} />}
            <span>{isLandscape ? 'خروج' : 'Landscape'}</span>
          </button>
        </div>
      </div>

      {/* Main Chart Body (dir="ltr" keeps Vertical Drawing Sidebar strictly on the LEFT) */}
      <div dir="ltr" className="relative flex-1 min-h-[280px] flex overflow-hidden bg-[#0b0f19]">
        {/* Phase 2: Sleek Left Vertical Drawing Sidebar */}
        <aside className="w-11 shrink-0 bg-gray-950/95 border-r border-gray-800/90 flex flex-col items-center py-2 gap-1.5 z-20">
          {DRAWING_TOOLS.map(({ id, label, Icon }) => {
            const active = activeTool === id;
            return (
              <button
                key={id}
                type="button"
                title={label}
                onClick={() => handleActivateDrawingTool(id)}
                className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors border ${
                  active
                    ? 'bg-amber-500/20 border-amber-500/60 text-amber-300'
                    : 'bg-gray-900/80 border-gray-800 text-gray-400 hover:text-white hover:border-gray-700'
                }`}
              >
                <Icon size={15} />
              </button>
            );
          })}

          <div className="w-6 h-px bg-gray-800 my-0.5" />

          <button
            type="button"
            title="Clear All Drawings"
            onClick={handleClearDrawings}
            className="w-8 h-8 rounded-lg flex items-center justify-center border border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 transition-colors"
          >
            <Trash2 size={15} />
          </button>
        </aside>

        {/* Chart Canvas Viewport + Floating Shape Edit Menu */}
        <div className="relative flex-1 min-w-0 h-full bg-[#0b0f19]">
          {/* Phase 3: Animated Top Shape Edit Menu */}
          <div
            className={`absolute top-2 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-950/95 border border-gray-700/90 shadow-2xl backdrop-blur-md transition-all duration-200 ease-out ${
              selectedOverlay
                ? 'opacity-100 translate-y-0 pointer-events-auto'
                : 'opacity-0 -translate-y-4 pointer-events-none'
            }`}
          >
            <div className="flex items-center gap-1.5">
              {SHAPE_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => handleChangeSelectedColor(color)}
                  aria-label={`Color ${color}`}
                  className={`w-4 h-4 rounded-full transition-transform ${
                    selectedOverlay?.color === color
                      ? 'ring-2 ring-white scale-110'
                      : 'opacity-80 hover:opacity-100 hover:scale-105'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <div className="w-px h-4 bg-gray-700" />
            <button
              type="button"
              onClick={handleDeleteSelectedOverlay}
              title="حذف شکل"
              className="p-1 rounded-full text-rose-400 hover:bg-rose-500/20 transition-colors"
            >
              <Trash2 size={14} />
            </button>
          </div>

          <div
            ref={containerRef}
            className="superchart-canvas w-full h-full"
            style={{ touchAction: 'none' }}
          />

          {(isLoading || isLoadingMore) && (
            <div
              dir="rtl"
              className="absolute top-3 right-3 z-20 px-2.5 py-1 rounded-lg bg-gray-950/90 border border-gray-800 text-[10px] text-amber-300 font-bold"
            >
              {isLoadingMore ? 'در حال بارگذاری کندل‌های قدیمی‌تر...' : 'در حال دریافت کندل‌های زنده...'}
            </div>
          )}

          {errorBanner && (
            <div
              dir="rtl"
              className="absolute inset-0 z-30 flex items-center justify-center bg-gray-950/85 backdrop-blur-sm p-4"
            >
              <div className="max-w-xs w-full rounded-2xl border border-rose-500/40 bg-gray-900 p-4 text-center space-y-3 shadow-2xl">
                <div className="text-2xl">{errorBanner.isVipError ? '🔒' : '⚠️'}</div>
                <p className="text-xs font-bold text-rose-300">{errorBanner.message}</p>
                {errorBanner.faMessage && (
                  <p className="text-[11px] text-gray-300">{errorBanner.faMessage}</p>
                )}
                {errorBanner.isVipError ? (
                  <button
                    type="button"
                    onClick={onOpenVipModal}
                    className="w-full py-2 rounded-xl bg-amber-500 text-gray-950 text-xs font-extrabold"
                  >
                    تمدید / خرید اشتراک VIP
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setRetryNonce((n) => n + 1)}
                    className="px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold"
                  >
                    تلاش مجدد ({errorBanner.attempt})
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SuperchartView;
