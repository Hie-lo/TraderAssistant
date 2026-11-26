import React, { useEffect, useRef, useState, useCallback } from 'react';
import { init, dispose } from 'klinecharts';
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
  { id: 'segment', label: 'خط روند' },
  { id: 'horizontalStraightLine', label: 'خط افقی' },
  { id: 'rayLine', label: 'اشعه (Ray)' },
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
    // Ignore WebView localStorage restrictions
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

const SuperchartView = ({ pairs = [], initialSymbol = 'BTCUSDT', onOpenVipModal }) => {
  const wrapperRef = useRef(null);
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const barsRef = useRef([]);
  const isRestoringRef = useRef(false);

  const [symbol, setSymbol] = useState(initialSymbol || 'BTCUSDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [activeTool, setActiveTool] = useState(null);
  const [activeIndicators, setActiveIndicators] = useState(() => {
    const saved = safeReadJson(INDICATORS_STORAGE_KEY, ['VOL']);
    return Array.isArray(saved) ? saved : ['VOL'];
  });
  const [isLandscape, setIsLandscape] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [errorBanner, setErrorBanner] = useState(null); // { message, isVipError, attempt }
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
        points: ov.points.map((pt) => ({
          timestamp: pt.timestamp,
          dataIndex: pt.dataIndex,
          value: pt.value,
        })),
      }));
    safeWriteJson(`${DRAWINGS_STORAGE_PREFIX}${symbolRef.current}`, serialized);
  }, []);

  const restoreDrawingsForSymbol = useCallback(
    (sym) => {
      const chart = chartRef.current;
      if (!chart) return;
      isRestoringRef.current = true;
      try {
        chart.removeOverlay();
        const saved = safeReadJson(`${DRAWINGS_STORAGE_PREFIX}${sym}`, []);
        if (Array.isArray(saved) && saved.length > 0) {
          saved.forEach((item) => {
            if (!item?.name || !Array.isArray(item.points) || item.points.length === 0) return;
            chart.createOverlay({
              name: item.name,
              points: item.points,
              onDrawEnd: () => persistDrawingsForCurrentSymbol(),
              onPressedMoveEnd: () => persistDrawingsForCurrentSymbol(),
              onRemoved: () => persistDrawingsForCurrentSymbol(),
            });
          });
        }
      } finally {
        isRestoringRef.current = false;
      }
    },
    [persistDrawingsForCurrentSymbol]
  );

  // Initialize klinecharts once and clean up strictly on unmount
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = init(container, {
      styles: {
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
        },
        xAxis: {
          axisLine: { color: '#334155' },
          tickText: { color: '#94a3b8' },
        },
        yAxis: {
          axisLine: { color: '#334155' },
          tickText: { color: '#94a3b8' },
        },
        crosshair: {
          horizontal: { line: { color: '#64748b' } },
          vertical: { line: { color: '#64748b' } },
        },
      },
    });

    chartRef.current = chart;

    // Restore persisted indicators on initial mount
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
      window.removeEventListener('resize', handleResize);
      observer?.disconnect();
      dispose(container);
      chartRef.current = null;
    };
  }, []);

  // Resize chart cleanly whenever portrait/landscape layout rotates
  useEffect(() => {
    const timer = window.setTimeout(() => {
      chartRef.current?.resize();
    }, 60);
    return () => window.clearTimeout(timer);
  }, [isLandscape]);

  // Strict VIP-gated klines fetch with AbortController + HTTP 503 exponential backoff retry
  useEffect(() => {
    let isMounted = true;
    let retryTimer = null;
    let attempt = 0;
    const abortController = new AbortController();

    const loadKlines = async () => {
      if (!isMounted) return;
      setIsLoading(true);
      try {
        const payload = await api.getMarketKlines(symbol, timeframe, 200, abortController.signal);
        if (!isMounted || abortController.signal.aborted) return;

        const bars = Array.isArray(payload?.bars) ? payload.bars : [];
        if (bars.length === 0) {
          const emptyErr = new Error('داده‌ای از صرافی دریافت نشد.');
          emptyErr.status = 503;
          throw emptyErr;
        }

        barsRef.current = bars;
        setErrorBanner(null);
        setIsLoading(false);

        const chart = chartRef.current;
        if (chart) {
          const tfMeta = TIMEFRAMES.find((t) => t.id === timeframe) || TIMEFRAMES[2];
          const pricePrecision = inferPrecision(bars);
          chart.setSymbol({ ticker: symbol, pricePrecision, volumePrecision: 2 });
          chart.setPeriod(tfMeta.period);
          chart.setDataLoader({
            getBars: ({ callback }) => {
              callback(barsRef.current, false);
            },
          });
          restoreDrawingsForSymbol(symbol);
        }
      } catch (err) {
        if (!isMounted || abortController.signal.aborted || err?.name === 'AbortError') return;

        setIsLoading(false);
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
          faMessage: `خطا در دریافت اطلاعات بازار از صرافی. تلاش مجدد تا ${Math.round(delayMs / 1000)} ثانیه دیگر...`,
          isVipError: false,
          attempt,
        });
        retryTimer = window.setTimeout(() => {
          if (isMounted) loadKlines();
        }, delayMs);
      }
    };

    loadKlines();

    return () => {
      isMounted = false;
      abortController.abort();
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, [symbol, timeframe, retryNonce, restoreDrawingsForSymbol]);

  const handleActivateDrawingTool = (toolId) => {
    const chart = chartRef.current;
    if (!chart) return;
    setActiveTool(toolId);
    chart.createOverlay({
      name: toolId,
      onDrawEnd: () => {
        setActiveTool(null);
        persistDrawingsForCurrentSymbol();
      },
      onPressedMoveEnd: () => persistDrawingsForCurrentSymbol(),
      onRemoved: () => persistDrawingsForCurrentSymbol(),
    });
  };

  const handleClearDrawings = () => {
    chartRef.current?.removeOverlay();
    safeWriteJson(`${DRAWINGS_STORAGE_PREFIX}${symbol}`, []);
    setActiveTool(null);
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
        isLandscape
          ? 'fullscreen-landscape bg-[#0b0f19] flex flex-col overflow-hidden'
          : 'flex-1 min-h-0 flex flex-col bg-[#0b0f19] overflow-hidden'
      }
    >
      {/* Top Toolbar: Symbol, Timeframes & Golden Landscape Toggle */}
      <div className="shrink-0 px-2.5 py-2 bg-gray-950/95 border-b border-gray-800 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-gray-900 border border-gray-700 text-amber-300 font-mono text-xs font-bold rounded-lg px-2 py-1 focus:outline-none focus:border-amber-500"
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
        </div>

        <button
          type="button"
          onClick={() => setIsLandscape((prev) => !prev)}
          className="px-2.5 py-1 rounded-lg bg-gradient-to-r from-amber-500 to-yellow-400 hover:brightness-110 text-gray-950 text-[10px] sm:text-xs font-extrabold shadow shadow-amber-500/20 shrink-0"
        >
          {isLandscape ? '✕ خروج از حالت افقی' : '📱 Landscape'}
        </button>
      </div>

      {/* Drawing Tools & Indicators Bar */}
      <div className="shrink-0 px-2.5 py-1.5 bg-gray-900/80 border-b border-gray-800/80 flex flex-wrap items-center justify-between gap-1.5 text-[10px]">
        <div className="flex items-center gap-1 flex-wrap">
          {DRAWING_TOOLS.map((tool) => (
            <button
              key={tool.id}
              type="button"
              onClick={() => handleActivateDrawingTool(tool.id)}
              className={`px-2 py-0.5 rounded border transition-colors ${
                activeTool === tool.id
                  ? 'bg-blue-600/25 border-blue-500 text-blue-300 font-bold'
                  : 'bg-gray-950 border-gray-800 text-gray-300 hover:border-gray-600'
              }`}
            >
              ✏️ {tool.label}
            </button>
          ))}
          <button
            type="button"
            onClick={handleClearDrawings}
            className="px-2 py-0.5 rounded border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"
          >
            🗑️ پاک‌سازی
          </button>
        </div>

        <div dir="ltr" className="flex items-center gap-1 flex-wrap">
          {INDICATORS.map((ind) => {
            const on = activeIndicators.includes(ind.id);
            return (
              <button
                key={ind.id}
                type="button"
                onClick={() => handleToggleIndicator(ind)}
                className={`px-1.5 py-0.5 rounded font-mono font-bold border transition-colors ${
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

      {/* Chart Viewport Container with touch-action: none */}
      <div className="relative flex-1 min-h-[280px] w-full bg-[#0b0f19]">
        <div
          ref={containerRef}
          className="superchart-canvas w-full h-full"
          style={{ touchAction: 'none' }}
        />

        {isLoading && (
          <div className="absolute top-3 left-3 z-20 px-2.5 py-1 rounded-lg bg-gray-950/90 border border-gray-800 text-[10px] text-amber-300 font-bold">
            در حال دریافت کندل‌های زنده...
          </div>
        )}

        {errorBanner && (
          <div className="absolute inset-0 z-30 flex items-center justify-center bg-gray-950/85 backdrop-blur-sm p-4">
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
  );
};

export default SuperchartView;
