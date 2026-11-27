import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
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
  Move,
  ChevronDown,
  Search,
  SlidersHorizontal,
} from 'lucide-react';
import { api } from '../api/client';
import CenteredModal from './CenteredModal';

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
  { id: 'MA', label: 'MA', desc: 'میانگین متحرک ساده (Moving Average)', isOverlay: true },
  { id: 'EMA', label: 'EMA', desc: 'میانگین متحرک نمایی (Exponential MA)', isOverlay: true },
  { id: 'BOLL', label: 'BOLL', desc: 'باندهای بولینگر (Bollinger Bands)', isOverlay: true },
  { id: 'VOL', label: 'VOL', desc: 'حجم معاملات (Volume)', isOverlay: false },
  { id: 'MACD', label: 'MACD', desc: 'مکدی و هیستوگرام مومنتوم', isOverlay: false },
  { id: 'RSI', label: 'RSI', desc: 'شاخص قدرت نسبی (RSI 14)', isOverlay: false },
];

const DRAWINGS_STORAGE_PREFIX = 'superchart_drawings_v1_';
const INDICATORS_STORAGE_KEY = 'superchart_indicators_v1';
const LEGEND_STORAGE_KEY = 'superchart_legend_visible_v1';
const THROTTLE_MS = 75;

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

const normalizeCandle = (raw) => {
  if (!raw) return null;
  const tsNum = Number(raw.timestamp);
  const timestamp = tsNum > 0 && tsNum < 1e12 ? tsNum * 1000 : tsNum;
  const open = Number(raw.open);
  const high = Number(raw.high);
  const low = Number(raw.low);
  const close = Number(raw.close);
  const volume = Number(raw.volume ?? 0);
  if (![timestamp, open, high, low, close].every(Number.isFinite)) return null;
  return { timestamp, open, high, low, close, volume: Number.isFinite(volume) ? volume : 0 };
};

export const buildSuperchartStyles = (showLegend, isLandscape) => ({
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
  overlay: {
    point: {
      color: '#3b82f6',
      borderColor: 'rgba(59, 130, 246, 0.35)',
      borderSize: 2,
      radius: 8,
      activeColor: '#60a5fa',
      activeBorderColor: 'rgba(96, 165, 250, 0.45)',
      activeBorderSize: 5,
      activeRadius: 11,
    },
    line: {
      style: 'solid',
      size: 2.5,
      color: '#3b82f6',
      dashedValue: [2, 2],
    },
  },
  xAxis: {
    axisLine: { color: '#334155' },
    tickText: { color: '#94a3b8', size: 10 },
  },
  yAxis: isLandscape
    ? {
        size: 76,
        axisLine: { color: '#475569', size: 1.5 },
        tickLine: { color: '#475569', length: 4 },
        tickText: { color: '#cbd5e1', size: 11, marginStart: 6, marginEnd: 8 },
      }
    : {
        size: 48,
        axisLine: { color: '#334155', size: 1 },
        tickLine: { color: '#334155', length: 2 },
        tickText: { color: '#94a3b8', size: 9, marginStart: 2, marginEnd: 3 },
      },
  crosshair: {
    horizontal: { line: { color: '#64748b' } },
    vertical: { line: { color: '#64748b' } },
  },
});

const mapRotatedTouch = (touch, rootBox, target) => {
  const clientX = rootBox.left + (touch.clientY - rootBox.top);
  const clientY = rootBox.top + (rootBox.right - touch.clientX);
  return new Touch({
    identifier: touch.identifier,
    target,
    clientX,
    clientY,
    pageX: clientX + window.scrollX,
    pageY: clientY + window.scrollY,
    screenX: clientX,
    screenY: clientY,
    radiusX: touch.radiusX || 1,
    radiusY: touch.radiusY || 1,
    rotationAngle: touch.rotationAngle || 0,
    force: touch.force || 1,
  });
};

const SuperchartView = ({
  pairs = [],
  marketPrices = {},
  initialSymbol = 'BTCUSDT',
  onOpenVipModal,
}) => {
  const wrapperRef = useRef(null);
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const wsRef = useRef(null);
  const isRestoringRef = useRef(false);
  const hasInitialDataRef = useRef(false);
  const dragCleanupRef = useRef(null);

  // Phase 4: Mutable tick buffer & throttle refs (zero React re-renders per tick)
  const latestTickRef = useRef(null);
  const lastFlushTimeRef = useRef(0);
  const rafIdRef = useRef(null);
  const throttleTimerRef = useRef(null);

  const [isChartReady, setIsChartReady] = useState(false);
  const [symbol, setSymbol] = useState(initialSymbol || 'BTCUSDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [activeTool, setActiveTool] = useState(null);
  const [selectedOverlay, setSelectedOverlay] = useState(null); // { id, color, paneId }
  const [dragHandlePos, setDragHandlePos] = useState(null); // { x, y }
  const [isDraggingHandle, setIsDraggingHandle] = useState(false);

  const [isSymbolModalOpen, setIsSymbolModalOpen] = useState(false);
  const [symbolSearch, setSymbolSearch] = useState('');
  const [isIndicatorsModalOpen, setIsIndicatorsModalOpen] = useState(false);

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

  const isCssRotatedRef = useRef(isCssRotated);
  isCssRotatedRef.current = isCssRotated;

  const selectedOverlayRef = useRef(selectedOverlay);
  selectedOverlayRef.current = selectedOverlay;

  const computeDragHandlePos = useCallback((overlayObj) => {
    const chart = chartRef.current;
    const container = containerRef.current;
    if (!chart || !container || !overlayObj?.id) {
      setDragHandlePos(null);
      return;
    }

    const found = chart.getOverlays({ id: overlayObj.id })?.[0];
    if (!found || !Array.isArray(found.points) || found.points.length === 0) {
      setDragHandlePos(null);
      return;
    }

    const paneId = found.paneId || overlayObj.paneId || 'candle_pane';
    const rawPixels = chart.convertToPixel(found.points, { paneId });
    const pixels = Array.isArray(rawPixels) ? rawPixels : [rawPixels];

    const xs = pixels.map((p) => p?.x).filter((v) => typeof v === 'number' && Number.isFinite(v));
    const ys = pixels.map((p) => p?.y).filter((v) => typeof v === 'number' && Number.isFinite(v));

    if (ys.length === 0) {
      setDragHandlePos(null);
      return;
    }

    const paneSize = chart.getSize(paneId) || { width: container.clientWidth, height: container.clientHeight };
    const maxW = Math.max(80, paneSize.width || container.clientWidth || 320);
    const maxH = Math.max(80, paneSize.height || container.clientHeight || 260);

    const avgX = xs.length > 0 ? xs.reduce((a, b) => a + b, 0) / xs.length : maxW * 0.5;
    const bottomY = Math.max(...ys) + 22;

    const clampedX = Math.min(Math.max(avgX, 24), maxW - 24);
    const clampedY = Math.min(Math.max(bottomY, 24), maxH - 22);
    setDragHandlePos({ x: clampedX, y: clampedY });
  }, []);

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
    (overlayConfig) => {
      const color = overlayConfig.styles?.line?.color || '#3b82f6';
      return {
        ...overlayConfig,
        styles: {
          line: { color, size: 2.5 },
          point: {
            color,
            borderColor: 'rgba(59, 130, 246, 0.35)',
            radius: 8,
            activeRadius: 11,
            activeBorderColor: color,
            activeBorderSize: 5,
          },
        },
        onDrawEnd: ({ overlay }) => {
          setActiveTool(null);
          persistDrawingsForCurrentSymbol();
          if (overlay) {
            const nextSel = {
              id: overlay.id,
              color: overlay.styles?.line?.color || color,
              paneId: overlay.paneId || 'candle_pane',
            };
            setSelectedOverlay(nextSel);
            computeDragHandlePos(nextSel);
          }
        },
        onPressedMoving: ({ overlay }) => {
          if (overlay && selectedOverlayRef.current?.id === overlay.id) {
            computeDragHandlePos(selectedOverlayRef.current);
          }
        },
        onPressedMoveEnd: ({ overlay }) => {
          persistDrawingsForCurrentSymbol();
          if (overlay && selectedOverlayRef.current?.id === overlay.id) {
            computeDragHandlePos(selectedOverlayRef.current);
          }
        },
        onRemoved: ({ overlay }) => {
          setSelectedOverlay((prev) => (prev?.id === overlay?.id ? null : prev));
          setDragHandlePos(null);
          persistDrawingsForCurrentSymbol();
        },
        onSelected: ({ overlay }) => {
          if (!overlay) return;
          const nextSel = {
            id: overlay.id,
            color: overlay.styles?.line?.color || '#3b82f6',
            paneId: overlay.paneId || 'candle_pane',
          };
          setSelectedOverlay(nextSel);
          computeDragHandlePos(nextSel);
        },
        onDeselected: ({ overlay }) => {
          setSelectedOverlay((prev) => {
            if (prev?.id === overlay?.id) {
              setDragHandlePos(null);
              return null;
            }
            return prev;
          });
        },
      };
    },
    [persistDrawingsForCurrentSymbol, computeDragHandlePos]
  );

  const restoreDrawingsForSymbol = useCallback(
    (sym) => {
      const chart = chartRef.current;
      if (!chart) return;
      isRestoringRef.current = true;
      try {
        chart.removeOverlay();
        setSelectedOverlay(null);
        setDragHandlePos(null);
        const saved = safeReadJson(`${DRAWINGS_STORAGE_PREFIX}${sym}`, []);
        if (Array.isArray(saved) && saved.length > 0) {
          saved.forEach((item) => {
            if (!item?.name || !Array.isArray(item.points) || item.points.length === 0) return;
            const color = item.color || '#3b82f6';
            chart.createOverlay(
              attachOverlayLifecycle({
                name: item.name,
                points: item.points,
                styles: { line: { color } },
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
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = init(container, {
      styles: buildSuperchartStyles(showLegend, isLandscape),
    });
    if (chart && typeof chart.updateData !== 'function') {
      chart.updateData = (candle) => {
        chart.getChartStore()?._addData(candle, 'update');
      };
    }
    chartRef.current = chart;
    setIsChartReady(Boolean(chart));

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

    const syncSelectedHandle = () => {
      if (selectedOverlayRef.current) {
        computeDragHandlePos(selectedOverlayRef.current);
      }
    };

    chart.subscribeAction('onScroll', syncSelectedHandle);
    chart.subscribeAction('onZoom', syncSelectedHandle);
    chart.subscribeAction('onPaneDrag', syncSelectedHandle);

    const handleResize = () => {
      chartRef.current?.resize();
      syncSelectedHandle();
    };

    let observer = null;
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(handleResize);
      observer.observe(container);
    }
    window.addEventListener('resize', handleResize);

    return () => {
      setIsChartReady(false);
      dragCleanupRef.current?.();
      window.removeEventListener('resize', handleResize);
      observer?.disconnect();
      chart.unsubscribeAction('onScroll', syncSelectedHandle);
      chart.unsubscribeAction('onZoom', syncSelectedHandle);
      chart.unsubscribeAction('onPaneDrag', syncSelectedHandle);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      dispose(container);
      chartRef.current = null;
    };
  }, [computeDragHandlePos]);

  // 2. Sync dynamic Y-axis thickness & OHLCV legend visibility without reloading data
  useEffect(() => {
    safeWriteJson(LEGEND_STORAGE_KEY, showLegend);
    const chart = chartRef.current;
    if (!chart) return undefined;
    chart.setStyles(buildSuperchartStyles(showLegend, isLandscape));
    const timer = window.setTimeout(() => {
      chartRef.current?.resize();
      if (selectedOverlayRef.current) {
        computeDragHandlePos(selectedOverlayRef.current);
      }
    }, 60);
    return () => window.clearTimeout(timer);
  }, [showLegend, isLandscape, isCssRotated, computeDragHandlePos]);

  // 3. Landscape Touch/Click/Mouse Coordinate Transformer
  // Maps physical portrait screen coordinates against chartRootEl.getBoundingClientRect()
  // so pan, pinch zoom, and overlay tap selection align 1:1 even with multiple panes.
  useEffect(() => {
    if (!isCssRotated) return undefined;

    let activeTouchTarget = null;

    const getChartRootBox = (container) => {
      const rootEl = container.firstElementChild || container;
      return rootEl.getBoundingClientRect();
    };

    const isUiControl = (target) => Boolean(target?.closest?.('[data-superchart-ui="true"]'));

    const handleTouch = (e) => {
      if (e.__landscapeMapped) return;
      const container = containerRef.current;
      if (!container) return;

      if (e.type === 'touchstart') {
        if (isUiControl(e.target) || !container.contains(e.target)) return;
        activeTouchTarget = e.target;
      }

      const targetEl = activeTouchTarget && container.contains(activeTouchTarget) ? activeTouchTarget : null;
      if (!targetEl) return;

      if ((e.type === 'touchend' || e.type === 'touchcancel') && e.touches.length === 0) {
        activeTouchTarget = null;
      }

      if (typeof Touch === 'undefined' || typeof TouchEvent === 'undefined') return;

      try {
        const rootBox = getChartRootBox(container);
        const mapList = (list) => Array.from(list || []).map((t) => mapRotatedTouch(t, rootBox, targetEl));

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
        // Ignore if WebView blocks synthetic TouchEvent construction
      }
    };

    const handleMouse = (e) => {
      if (e.__landscapeMapped) return;
      if (isUiControl(e.target)) return;
      const container = containerRef.current;
      if (!container || !container.contains(e.target)) return;

      const rootBox = getChartRootBox(container);
      const clientX = rootBox.left + (e.clientY - rootBox.top);
      const clientY = rootBox.top + (rootBox.right - e.clientX);

      e.stopImmediatePropagation();
      const mappedMouse = new MouseEvent(e.type, {
        bubbles: true,
        cancelable: e.cancelable,
        view: window,
        detail: e.detail,
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
    document.addEventListener('click', handleMouse, true);
    document.addEventListener('dblclick', handleMouse, true);

    return () => {
      document.removeEventListener('touchstart', handleTouch, touchOpts);
      document.removeEventListener('touchmove', handleTouch, touchOpts);
      document.removeEventListener('touchend', handleTouch, touchOpts);
      document.removeEventListener('touchcancel', handleTouch, touchOpts);
      document.removeEventListener('mousedown', handleMouse, true);
      document.removeEventListener('mousemove', handleMouse, true);
      document.removeEventListener('mouseup', handleMouse, true);
      document.removeEventListener('click', handleMouse, true);
      document.removeEventListener('dblclick', handleMouse, true);
    };
  }, [isCssRotated]);

  // 4. Phase 1 Historical & Infinite Scroll DataLoader
  useEffect(() => {
    const chart = chartRef.current;
    if (!isChartReady || !chart) return undefined;

    let isEffectActive = true;
    let retryTimer = null;
    let attempt = 0;
    const activeControllers = new Set();
    hasInitialDataRef.current = false;

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

          const bars = Array.isArray(payload?.bars) ? payload.bars.map(normalizeCandle).filter(Boolean) : [];
          if (type === 'init' && bars.length === 0) {
            const emptyErr = new Error('داده‌ای از صرافی دریافت نشد.');
            emptyErr.status = 503;
            throw emptyErr;
          }

          setErrorBanner(null);
          if (type === 'init') {
            setIsLoading(false);
            const precision = inferPrecision(bars);
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
            hasInitialDataRef.current = true;
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
      hasInitialDataRef.current = false;
      if (retryTimer) window.clearTimeout(retryTimer);
      activeControllers.forEach((ctrl) => ctrl.abort());
      activeControllers.clear();
    };
  }, [isChartReady, symbol, timeframe, retryNonce, restoreDrawingsForSymbol]);

  // 5. Phase 4: High-Performance Throttled RAF Buffer + WebSocket + Auto-Reconnect
  useEffect(() => {
    if (!isChartReady || !chartRef.current) return undefined;

    let isActive = true;
    let ws = null;
    let reconnectTimer = null;
    const pollController = new AbortController();

    const flushBufferedTick = () => {
      rafIdRef.current = null;
      if (!isActive || !chartRef.current || !hasInitialDataRef.current) return;
      const buffered = latestTickRef.current;
      if (!buffered) return;

      const now = performance.now();
      const elapsed = now - lastFlushTimeRef.current;
      if (elapsed < THROTTLE_MS) {
        if (!throttleTimerRef.current) {
          throttleTimerRef.current = window.setTimeout(() => {
            throttleTimerRef.current = null;
            if (isActive && !rafIdRef.current) {
              rafIdRef.current = window.requestAnimationFrame(flushBufferedTick);
            }
          }, THROTTLE_MS - elapsed);
        }
        return;
      }

      latestTickRef.current = null;
      lastFlushTimeRef.current = now;
      console.log('LIVE DATA RECEIVED:', buffered);
      chartRef.current.updateData(buffered);
    };

    const enqueueLiveCandle = (raw) => {
      const normalized = normalizeCandle(raw);
      if (!normalized || !hasInitialDataRef.current) return;
      latestTickRef.current = normalized;
      if (!rafIdRef.current) {
        rafIdRef.current = window.requestAnimationFrame(flushBufferedTick);
      }
    };

    const connectWebSocket = () => {
      if (!isActive) return;
      try {
        ws = new WebSocket(api.getMarketStreamUrl(symbol, timeframe));
        wsRef.current = ws;

        ws.onmessage = (evt) => {
          if (!isActive) return;
          try {
            const parsed = JSON.parse(evt.data);
            enqueueLiveCandle(parsed?.bar || parsed);
          } catch (parseErr) {
            // Ignore malformed JSON frames
          }
        };

        ws.onerror = () => {
          if (ws && ws.readyState !== WebSocket.CLOSED) {
            ws.close();
          }
        };

        ws.onclose = () => {
          if (!isActive) return;
          wsRef.current = null;
          reconnectTimer = window.setTimeout(connectWebSocket, 3000);
        };
      } catch (wsErr) {
        reconnectTimer = window.setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    // Resilient polling fallback while WebSocket is reconnecting/unavailable
    const pollInterval = window.setInterval(async () => {
      if (!isActive || !hasInitialDataRef.current) return;
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

      try {
        const res = await api.getMarketKlines(symbol, timeframe, 2, null, pollController.signal);
        if (!isActive || pollController.signal.aborted) return;
        const bars = Array.isArray(res?.bars) ? res.bars : [];
        if (bars.length > 0) {
          enqueueLiveCandle(bars[bars.length - 1]);
        }
      } catch (err) {
        // Ignore transient fallback errors; WS auto-reconnect continues
      }
    }, 3000);

    return () => {
      isActive = false;
      latestTickRef.current = null;
      if (rafIdRef.current) {
        window.cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      if (throttleTimerRef.current) {
        window.clearTimeout(throttleTimerRef.current);
        throttleTimerRef.current = null;
      }
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      window.clearInterval(pollInterval);
      pollController.abort();
      if (ws) {
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
      }
      wsRef.current = null;
    };
  }, [isChartReady, symbol, timeframe]);

  // Memory-safe Floating Drag Handle pointer/touch handler
  const startHandleDrag = (startEvent) => {
    startEvent.stopPropagation();
    const chart = chartRef.current;
    const container = containerRef.current;
    const sel = selectedOverlayRef.current;
    if (!chart || !container || !sel?.id) return;

    const overlayObj = chart.getOverlays({ id: sel.id })?.[0];
    if (!overlayObj || !Array.isArray(overlayObj.points) || overlayObj.points.length === 0) return;

    const paneId = overlayObj.paneId || sel.paneId || 'candle_pane';
    const rawPixels = chart.convertToPixel(overlayObj.points, { paneId });
    const startPixels = (Array.isArray(rawPixels) ? rawPixels : [rawPixels]).map((pt) => ({
      x: Number(pt?.x ?? 0),
      y: Number(pt?.y ?? 0),
    }));

    const chartRootEl = container.firstElementChild || container;
    const getCanvasXY = (ev) => {
      const pt = ev.touches?.[0] || ev.changedTouches?.[0] || ev;
      const box = chartRootEl.getBoundingClientRect();
      if (isCssRotatedRef.current) {
        return {
          x: box.left + (pt.clientY - box.top) - box.left,
          y: box.top + (box.right - pt.clientX) - box.top,
        };
      }
      return {
        x: pt.clientX - box.left,
        y: pt.clientY - box.top,
      };
    };

    const origin = getCanvasXY(startEvent);
    setIsDraggingHandle(true);

    const onMove = (moveEv) => {
      if (moveEv.cancelable) moveEv.preventDefault();
      const curr = getCanvasXY(moveEv);
      const dx = curr.x - origin.x;
      const dy = curr.y - origin.y;

      const shiftedPixels = startPixels.map((p) => ({ x: p.x + dx, y: p.y + dy }));
      const converted = chart.convertFromPixel(shiftedPixels, { paneId });
      const nextPoints = Array.isArray(converted) ? converted : [converted];

      chart.overrideOverlay({
        id: sel.id,
        points: nextPoints,
      });
      computeDragHandlePos(sel);
    };

    const cleanup = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onEnd);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('touchend', onEnd);
      window.removeEventListener('touchcancel', onEnd);
      dragCleanupRef.current = null;
      setIsDraggingHandle(false);
    };

    const onEnd = () => {
      cleanup();
      persistDrawingsForCurrentSymbol();
    };

    dragCleanupRef.current?.();
    dragCleanupRef.current = cleanup;
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onEnd);
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('touchend', onEnd);
    window.addEventListener('touchcancel', onEnd);
  };

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
    setDragHandlePos(null);
    safeWriteJson(`${DRAWINGS_STORAGE_PREFIX}${symbol}`, []);
    setActiveTool(null);
  };

  const handleChangeSelectedColor = (color) => {
    const chart = chartRef.current;
    if (!chart || !selectedOverlay) return;
    chart.overrideOverlay({
      id: selectedOverlay.id,
      styles: {
        line: { color, size: 2.5 },
        point: {
          color,
          borderColor: color,
          activeBorderColor: color,
          radius: 8,
          activeRadius: 11,
          activeBorderSize: 5,
        },
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
    setDragHandlePos(null);
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

  const pairOptions = useMemo(
    () =>
      pairs.length > 0
        ? pairs
        : [
            { symbol: 'BTCUSDT', label: 'BTC / USDT', base: 'BTC', icon: '₿', color: 'text-yellow-500 bg-yellow-500/10', defaultPrice: '64250.00' },
            { symbol: 'ETHUSDT', label: 'ETH / USDT', base: 'ETH', icon: 'Ξ', color: 'text-indigo-400 bg-indigo-500/10', defaultPrice: '3420.00' },
          ],
    [pairs]
  );

  const activePairObj = useMemo(
    () => pairOptions.find((p) => p.symbol === symbol) || pairOptions[0],
    [pairOptions, symbol]
  );

  const filteredPairs = useMemo(() => {
    const q = symbolSearch.trim().toLowerCase();
    if (!q) return pairOptions;
    return pairOptions.filter(
      (p) =>
        p.symbol.toLowerCase().includes(q) ||
        (p.label && p.label.toLowerCase().includes(q)) ||
        (p.base && p.base.toLowerCase().includes(q))
    );
  }, [pairOptions, symbolSearch]);

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
      {/* Top Toolbar: Centered Symbol Selector Button, Timeframes, Indicators Button, Legend Eye & Landscape */}
      <div className="shrink-0 px-2 py-1.5 bg-gray-950/95 border-b border-gray-800 flex flex-wrap items-center justify-between gap-1.5">
        <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
          {/* TradingView-style Symbol Modal Trigger */}
          <button
            type="button"
            onClick={() => {
              setSymbolSearch('');
              setIsSymbolModalOpen(true);
            }}
            className="flex items-center gap-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-700/80 px-2 py-1 rounded-lg text-[11px] font-bold text-white transition-colors"
          >
            <span className={`w-4 h-4 rounded flex items-center justify-center text-[9px] font-bold shrink-0 ${activePairObj?.color || 'text-amber-400 bg-amber-500/10'}`}>
              {activePairObj?.icon || '•'}
            </span>
            <span className="font-mono text-amber-300">{activePairObj?.label || symbol}</span>
            <ChevronDown size={12} className="text-gray-400" />
          </button>

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

          <button
            type="button"
            onClick={() => setIsIndicatorsModalOpen(true)}
            className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-900 hover:bg-gray-800 border border-gray-700/80 text-[10px] font-bold text-emerald-300 transition-colors"
          >
            <SlidersHorizontal size={12} />
            <span>اندیکاتورها ({activeIndicators.length})</span>
          </button>
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
        {/* Sleek Left Vertical Drawing Sidebar */}
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

        {/* Chart Canvas Viewport + Floating Shape Edit Menu + Dedicated Floating Move Handle */}
        <div className="relative flex-1 min-w-0 h-full bg-[#0b0f19]">
          {/* Animated Top Shape Edit Menu */}
          <div
            data-superchart-ui="true"
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

          {/* Dedicated Floating Move/Drag Handle directly below selected shape */}
          {selectedOverlay && dragHandlePos && (
            <button
              type="button"
              data-superchart-ui="true"
              onMouseDown={startHandleDrag}
              onTouchStart={startHandleDrag}
              title="Drag to Move Shape"
              style={{
                left: `${dragHandlePos.x}px`,
                top: `${dragHandlePos.y}px`,
                touchAction: 'none',
              }}
              className={`absolute -translate-x-1/2 -translate-y-1/2 z-40 w-8 h-8 rounded-full border flex items-center justify-center shadow-lg transition-colors ${
                isDraggingHandle
                  ? 'bg-amber-500 border-amber-300 text-gray-950 scale-110 cursor-grabbing'
                  : 'bg-gray-950/95 border-amber-500/60 text-amber-300 hover:bg-amber-500/20 cursor-grab'
              }`}
            >
              <Move size={14} />
            </button>
          )}

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
              data-superchart-ui="true"
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

      {/* Phase 3: Centered Symbol Selector Modal */}
      <CenteredModal
        isOpen={isSymbolModalOpen}
        onClose={() => setIsSymbolModalOpen(false)}
        title="انتخاب نماد معاملاتی"
        subtitle="ارز مورد نظر را جستجو و انتخاب کنید"
      >
        <div className="space-y-3">
          <div className="relative">
            <input
              type="text"
              value={symbolSearch}
              onChange={(e) => setSymbolSearch(e.target.value)}
              placeholder="جستجوی نماد (مثلاً BTC)..."
              autoFocus
              className="w-full bg-gray-950 border border-gray-700 rounded-xl pr-8 pl-3 py-2 text-xs text-white outline-none focus:border-amber-500"
            />
            <Search size={14} className="text-gray-500 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          <div className="max-h-64 overflow-y-auto space-y-1 pr-0.5">
            {filteredPairs.length === 0 ? (
              <div className="text-xs text-gray-500 text-center py-6">
                نمادی با این نام یافت نشد
              </div>
            ) : (
              filteredPairs.map((pair) => {
                const rowPrice = marketPrices[pair.symbol] || pair.defaultPrice || '0.00';
                const isSelected = pair.symbol === symbol;
                return (
                  <button
                    key={pair.symbol}
                    type="button"
                    onClick={() => {
                      setSymbol(pair.symbol);
                      setIsSymbolModalOpen(false);
                      setSymbolSearch('');
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition-colors ${
                      isSelected
                        ? 'bg-amber-500/15 border border-amber-500/40 text-amber-300 font-bold'
                        : 'hover:bg-gray-800/80 text-gray-200 border border-transparent'
                    }`}
                  >
                    <span className="flex items-center gap-2.5">
                      <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0 ${pair.color || 'text-amber-400 bg-amber-500/10'}`}>
                        {pair.icon || '•'}
                      </span>
                      <span>{pair.label || pair.symbol}</span>
                    </span>
                    <span dir="ltr" className="font-mono text-[11px] text-gray-300">
                      ${rowPrice}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </CenteredModal>

      {/* Phase 3: Centered Indicators Modal */}
      <CenteredModal
        isOpen={isIndicatorsModalOpen}
        onClose={() => setIsIndicatorsModalOpen(false)}
        title="اندیکاتورهای تکنیکال"
        subtitle="نمایش یا مخفی‌سازی شاخص‌ها روی سوپرچارت"
      >
        <div className="space-y-2">
          {INDICATORS.map((ind) => {
            const enabled = activeIndicators.includes(ind.id);
            return (
              <button
                key={ind.id}
                type="button"
                onClick={() => handleToggleIndicator(ind)}
                className={`w-full flex items-center justify-between p-3 rounded-xl border transition-colors text-right ${
                  enabled
                    ? 'bg-emerald-500/10 border-emerald-500/40'
                    : 'bg-gray-950/70 border-gray-800 hover:border-gray-700'
                }`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span dir="ltr" className="font-mono text-xs font-extrabold text-white">
                      {ind.label}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                      {ind.isOverlay ? 'روی کندل' : 'پنجره مجزا'}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-400 mt-0.5 truncate">{ind.desc}</p>
                </div>

                <div
                  dir="ltr"
                  className={`w-10 h-5 rounded-full p-0.5 transition-colors shrink-0 ${
                    enabled ? 'bg-emerald-500' : 'bg-gray-700'
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full bg-white shadow transition-transform ${
                      enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </CenteredModal>
    </div>
  );
};

export default SuperchartView;
