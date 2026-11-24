import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { api } from './api/client';

const FALLBACK_PAIRS = [
  { symbol: 'BTCUSDT', label: 'BTC / USDT', base: 'BTC', icon: '₿', color: 'text-yellow-500 bg-yellow-500/10', defaultPrice: '64250.00', step: 50 },
  { symbol: 'ETHUSDT', label: 'ETH / USDT', base: 'ETH', icon: 'Ξ', color: 'text-indigo-400 bg-indigo-500/10', defaultPrice: '3420.00', step: 5 },
  { symbol: 'SOLUSDT', label: 'SOL / USDT', base: 'SOL', icon: '◎', color: 'text-purple-400 bg-purple-500/10', defaultPrice: '148.50', step: 0.5 },
  { symbol: 'BNBUSDT', label: 'BNB / USDT', base: 'BNB', icon: '❖', color: 'text-amber-400 bg-amber-500/10', defaultPrice: '585.00', step: 1 },
  { symbol: 'TONUSDT', label: 'TON / USDT', base: 'TON', icon: '💎', color: 'text-sky-400 bg-sky-500/10', defaultPrice: '5.45', step: 0.05 },
  { symbol: 'XRPUSDT', label: 'XRP / USDT', base: 'XRP', icon: '✕', color: 'text-gray-300 bg-gray-500/10', defaultPrice: '0.58', step: 0.005 },
];

const FALLBACK_STRATEGIES = [
  'Price Action',
  'Smart Money / ICT',
  'Breakout',
  'RSI Divergence',
  'Support & Resistance',
  'Scalp / Momentum',
  'Fibonacci Retracement',
  'EMA Crossover',
  'Order Block / FVG',
  'Liquidity Sweep'
];

const INFO_TOOLTIPS = {
  risk: {
    title: 'مقدار ریسک (Risk)',
    desc: 'حداکثر مبلغ یا درصدی از کل موجودی که حاضرید در صورت فعال شدن حد ضرر (SL) در این معامله از دست بدهید.'
  },
  leverage: {
    title: 'اهرم معاملاتی (Leverage)',
    desc: 'ضریب اهرم فقط مارجین درگیر شما را کم یا زیاد می‌کند و تاثیری روی مقدار ضرر شما در نقطه استاپ‌لاس ندارد.'
  },
  margin: {
    title: 'مارجین درگیر (Required Margin)',
    desc: 'مقدار پولی که صرافی از موجودی حساب شما برای باز کردن این پوزیشن قفل می‌کند (ارزش کل پوزیشن تقسیم بر اهرم).'
  },
  size: {
    title: 'حجم پوزیشن (Position Size)',
    desc: 'تعداد واحد ارزی که باید در صرافی بخرید یا بفروشید تا در صورت برخورد به حد ضرر، دقیقاً به اندازه ریسک مشخص‌شده ضرر کنید.'
  },
  value: {
    title: 'ارزش کل پوزیشن (Position Value)',
    desc: 'ارزش دلاری کل معامله شما پس از اعمال ضریب اهرم (حجم پوزیشن ضربدر قیمت ورود).'
  },
  rr: {
    title: 'ریسک به ریوارد (R/R Ratio)',
    desc: 'نسبت سود احتمالی به ضرر احتمالی. مثلاً 1:2.5 یعنی سود شما در حد سود، ۲.۵ برابرِ ریسک شما در حد ضرر است.'
  }
};



const EXTRA_PAIR_META = {
  DOGEUSDT: { icon: 'Ð', color: 'text-amber-300 bg-amber-500/10' },
  ADAUSDT: { icon: '₳', color: 'text-sky-400 bg-sky-500/10' },
  AVAXUSDT: { icon: '▲', color: 'text-rose-400 bg-rose-500/10' },
  LINKUSDT: { icon: '⬡', color: 'text-blue-400 bg-blue-500/10' },
  SUIUSDT: { icon: '💧', color: 'text-cyan-400 bg-cyan-500/10' },
  PEPEUSDT: { icon: '🐸', color: 'text-emerald-400 bg-emerald-500/10' },
  TRXUSDT: { icon: '◈', color: 'text-red-400 bg-red-500/10' },
  LTCUSDT: { icon: 'Ł', color: 'text-slate-300 bg-slate-500/10' }
};

const PAIR_META_MAP = FALLBACK_PAIRS.reduce((acc, p) => {
  acc[p.symbol] = { icon: p.icon, color: p.color, step: p.step };
  return acc;
}, { ...EXTRA_PAIR_META });

const DYNAMIC_BADGE_COLORS = [
  'text-blue-400 bg-blue-500/10',
  'text-emerald-400 bg-emerald-500/10',
  'text-purple-400 bg-purple-500/10',
  'text-amber-400 bg-amber-500/10',
  'text-cyan-400 bg-cyan-500/10',
  'text-rose-400 bg-rose-500/10'
];

const formatPairPrice = (raw) => {
  const num = parseFloat(raw);
  if (isNaN(num) || num <= 0) return '0.00';
  if (num < 0.001) return num.toFixed(8);
  if (num < 0.1) return num.toFixed(6);
  if (num < 10) return num.toFixed(4);
  return num.toFixed(2);
};

const inferPriceStep = (raw) => {
  const num = parseFloat(raw);
  if (isNaN(num) || num <= 0) return 1;
  if (num >= 10000) return 50;
  if (num >= 1000) return 5;
  if (num >= 100) return 1;
  if (num >= 10) return 0.1;
  if (num >= 1) return 0.01;
  if (num >= 0.01) return 0.001;
  if (num >= 0.0001) return 0.00001;
  return 0.0000001;
};

const buildDynamicPair = (symbol, rawPrice) => {
  const base = symbol.replace(/USDT$/, '');
  const meta = PAIR_META_MAP[symbol];
  const colorIdx = base.split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % DYNAMIC_BADGE_COLORS.length;
  return {
    symbol,
    label: `${base} / USDT`,
    base,
    icon: meta?.icon || base.slice(0, 2),
    color: meta?.color || DYNAMIC_BADGE_COLORS[colorIdx],
    defaultPrice: formatPairPrice(rawPrice),
    step: meta?.step || inferPriceStep(rawPrice)
  };
};

const getTelegramUser = () => {
  try {
    return window.Telegram?.WebApp?.initDataUnsafe?.user || null;
  } catch (e) {
    return null;
  }
};

const App = () => {
  // --- Navigation & User State ---
  const [activeTab, setActiveTab] = useState('home'); // 'home' | 'calc' | 'journal' | 'portfolio' | 'empty'
  const [userName, setUserName] = useState(() => {
    const tg = getTelegramUser();
    if (tg?.first_name) {
      return tg.last_name ? `${tg.first_name} ${tg.last_name}` : tg.first_name;
    }
    return 'معامله‌گر';
  });
  const [userPhoto, setUserPhoto] = useState(() => {
    return getTelegramUser()?.photo_url || null;
  });

  // --- Dynamic Pairs & Strategies from Backend ---
  const [pairs, setPairs] = useState(FALLBACK_PAIRS);
  const [pairsLoading, setPairsLoading] = useState(false);
  const [marketPrices, setMarketPrices] = useState({});
  const marketPricesRef = useRef({});
  const exchangePairsLoadedRef = useRef(false);
  const activePairsSetRef = useRef(new Set(FALLBACK_PAIRS.map((p) => p.symbol)));
  const [defaultStrategies, setDefaultStrategies] = useState(FALLBACK_STRATEGIES);
  const [customStrategies, setCustomStrategies] = useState([]);
  const [maxLeverageLimit, setMaxLeverageLimit] = useState(2000);

  // --- Pair Selector & Live Price State ---
  const [selectedPair, setSelectedPair] = useState(FALLBACK_PAIRS[0]);
  const [isPairDropdownOpen, setIsPairDropdownOpen] = useState(false);
  const [pairSearch, setPairSearch] = useState('');
  const [livePrice, setLivePrice] = useState(FALLBACK_PAIRS[0].defaultPrice);
  const [priceColor, setPriceColor] = useState('text-gray-200');

  // --- Calculator Inputs State ---
  const [positionSide, setPositionSide] = useState('LONG'); // 'LONG' | 'SHORT'
  const [balance, setBalance] = useState('1000');
  const [leverage, setLeverage] = useState(10);
  const [riskType, setRiskType] = useState('%'); // '%' or '$'
  const [riskValue, setRiskValue] = useState('2');
  const [balanceEmptyNotice, setBalanceEmptyNotice] = useState(false);
  const [entryPrice, setEntryPrice] = useState('');
  const [stopLossPrice, setStopLossPrice] = useState('');
  const [takeProfitPrice, setTakeProfitPrice] = useState('');
  const [saveSuccessToast, setSaveSuccessToast] = useState(false);
  const [activeInfoKey, setActiveInfoKey] = useState(null);

  // --- Journal & Strategy State (strictly empty for new users) ---
  const [trades, setTrades] = useState([]);
  const [openStatusMenuId, setOpenStatusMenuId] = useState(null);
  const [selectedTradeId, setSelectedTradeId] = useState(null);
  const [draftTrade, setDraftTrade] = useState(null);
  const [detailSaveToast, setDetailSaveToast] = useState(false);
  const [isStrategyBarOpen, setIsStrategyBarOpen] = useState(false);
  const [newStrategyInput, setNewStrategyInput] = useState('');
  const [strategySearch, setStrategySearch] = useState('');
  const [isChartZoomOpen, setIsChartZoomOpen] = useState(false);
  const [isUploadingChart, setIsUploadingChart] = useState(false);
  const fileInputRef = useRef(null);

  // --- 1. Load Initial Bootstrap Data from Backend & Sync Telegram User ---
  useEffect(() => {
    // Auto-expand window to maximum available dimensions in Telegram Desktop & Mobile
    if (typeof window !== 'undefined' && window.Telegram?.WebApp) {
      try {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        if (window.Telegram.WebApp.isFullscreen && typeof window.Telegram.WebApp.exitFullscreen === 'function') {
          window.Telegram.WebApp.exitFullscreen();
        }
        if (window.Telegram.WebApp.setHeaderColor) {
          window.Telegram.WebApp.setHeaderColor('#020617');
        }
        if (window.Telegram.WebApp.setBackgroundColor) {
          window.Telegram.WebApp.setBackgroundColor('#020617');
        }
      } catch (e) {
        console.warn('Telegram WebApp expand failed:', e);
      }
    }

    const tg = getTelegramUser();
    if (tg?.first_name) {
      const fullName = tg.last_name ? `${tg.first_name} ${tg.last_name}` : tg.first_name;
      setUserName(fullName);
    }
    if (tg?.photo_url) {
      setUserPhoto(tg.photo_url);
    }

    const loadBootstrap = async () => {
      try {
        const data = await api.getBootstrap();
        if (data.user?.first_name && !getTelegramUser()?.first_name) {
          setUserName(data.user.first_name);
        }
        if (data.user?.photo_url && !getTelegramUser()?.photo_url) {
          setUserPhoto(data.user.photo_url);
        }
        if (data.user?.default_balance) {
          setBalance(data.user.default_balance);
        }
        if (data.config?.pairs?.length > 0 && !exchangePairsLoadedRef.current) {
          const normalizedPairs = data.config.pairs.map((p) => ({
            ...p,
            defaultPrice: p.defaultPrice || p.default_price || '0.00',
            step: p.step || inferPriceStep(p.defaultPrice || p.default_price)
          }));
          setPairs(normalizedPairs);
          setSelectedPair((prev) => normalizedPairs.find((p) => p.symbol === prev.symbol) || normalizedPairs[0]);
          // Bootstrap fallback pair price handled above if exchange pairs not yet loaded
          // Keep selectedPair synchronized
          setLivePrice((prev) => prev || data.config.pairs[0].default_price || '64250.00');
        }
        if (data.config?.default_strategies?.length > 0) {
          setDefaultStrategies(data.config.default_strategies);
        }
        if (data.config?.max_leverage) {
          setMaxLeverageLimit(data.config.max_leverage);
        }
        if (data.custom_strategies) {
          setCustomStrategies(data.custom_strategies);
        }
        if (Array.isArray(data.trades)) {
          setTrades(data.trades);
        }
      } catch (err) {
        console.warn('Bootstrap load failed, using local fallbacks:', err);
      }
    };
    loadBootstrap();
  }, []);

  // --- Drag-to-Scroll State for Market Ticker ---
  const tickerRef = useRef(null);
  const isDraggingTickerRef = useRef(false);
  const dragStartXRef = useRef(0);
  const scrollLeftStartRef = useRef(0);
  const hasDraggedRef = useRef(false);

  const handleTickerMouseDown = (e) => {
    if (!tickerRef.current) return;
    isDraggingTickerRef.current = true;
    hasDraggedRef.current = false;
    dragStartXRef.current = e.pageX - tickerRef.current.offsetLeft;
    scrollLeftStartRef.current = tickerRef.current.scrollLeft;
  };

  const handleTickerMouseMove = (e) => {
    if (!isDraggingTickerRef.current || !tickerRef.current) return;
    e.preventDefault();
    const x = e.pageX - tickerRef.current.offsetLeft;
    const walk = (x - dragStartXRef.current) * 1.5;
    if (Math.abs(walk) > 5) {
      hasDraggedRef.current = true;
    }
    tickerRef.current.scrollLeft = scrollLeftStartRef.current - walk;
  };

  const handleTickerMouseUpOrLeave = () => {
    isDraggingTickerRef.current = false;
  };

  // --- Keep active pair symbol set synced for fast !miniTicker@arr filtering ---
  useEffect(() => {
    activePairsSetRef.current = new Set((pairs || FALLBACK_PAIRS).map((p) => p.symbol));
  }, [pairs]);

  // --- Fetch All Active Trading Pairs Dynamically from Binance Exchange API ---
  useEffect(() => {
    const controller = new AbortController();
    let isCancelled = false;

    const fetchDynamicPairs = async () => {
      setPairsLoading(true);
      const endpoints = [
        'https://api.binance.com/api/v3/ticker/24hr',
        'https://data-api.binance.vision/api/v3/ticker/24hr'
      ];

      for (const url of endpoints) {
        try {
          const res = await fetch(url, { signal: controller.signal });
          if (!res.ok) continue;
          const tickers = await res.json();
          if (!Array.isArray(tickers) || isCancelled) return;

          const excludedRegex = /^(USDC|FDUSD|TUSD|USDP|BUSD|DAI|EUR|GBP|AUD|TRY|BRL|ARS|PAXG|AEUR|USDE|EURI)USDT$|.*(UP|DOWN|BULL|BEAR)USDT$/i;
          const activeUsdtPairs = tickers
            .filter((t) => {
              if (!t?.symbol || !t.symbol.endsWith('USDT')) return false;
              if (excludedRegex.test(t.symbol)) return false;
              const price = parseFloat(t.lastPrice);
              const vol = parseFloat(t.quoteVolume);
              return !isNaN(price) && price > 0 && !isNaN(vol) && vol > 100000;
            })
            .sort((a, b) => parseFloat(b.quoteVolume) - parseFloat(a.quoteVolume))
            .slice(0, 300)
            .map((t) => {
              const pairObj = buildDynamicPair(t.symbol, t.lastPrice);
              marketPricesRef.current[t.symbol] = pairObj.defaultPrice;
              return pairObj;
            });

          if (activeUsdtPairs.length > 0 && !isCancelled) {
            exchangePairsLoadedRef.current = true;
            setPairs(activeUsdtPairs);
            setMarketPrices({ ...marketPricesRef.current });
            setSelectedPair((prev) => activeUsdtPairs.find((p) => p.symbol === prev.symbol) || activeUsdtPairs[0]);
            return;
          }
        } catch (err) {
          if (err.name === 'AbortError') return;
        }
      }
      if (!isCancelled) {
        console.warn('Dynamic exchange pair fetch failed, keeping fallback list.');
      }
    };

    fetchDynamicPairs().finally(() => {
      if (!isCancelled) setPairsLoading(false);
    });

    return () => {
      isCancelled = true;
      controller.abort();
    };
  }, []);

  // --- Combined All-Market Live Ticker Stream (!miniTicker@arr) for Dropdown & Home Strip ---
  useEffect(() => {
    let isCancelled = false;
    let tickerWs = null;

    try {
      tickerWs = new WebSocket('wss://stream.binance.com:9443/ws/!miniTicker@arr');
      tickerWs.onmessage = (event) => {
        if (isCancelled) return;
        try {
          const items = JSON.parse(event.data);
          if (!Array.isArray(items)) return;
          const activeSet = activePairsSetRef.current;
          for (let i = 0; i < items.length; i++) {
            const item = items[i];
            if (item?.s && activeSet.has(item.s)) {
              const formatted = formatPairPrice(item.c);
              if (formatted !== '0.00') {
                marketPricesRef.current[item.s] = formatted;
              }
            }
          }
        } catch (e) {
          // Ignore malformed ticker payload
        }
      };
      tickerWs.onerror = () => {};
    } catch (e) {
      // Fallback gracefully if stream blocked
    }

    return () => {
      isCancelled = true;
      if (tickerWs) {
        tickerWs.onopen = null;
        tickerWs.onmessage = null;
        tickerWs.onerror = null;
        tickerWs.onclose = null;
        if (tickerWs.readyState === WebSocket.OPEN || tickerWs.readyState === WebSocket.CONNECTING) {
          tickerWs.close();
        }
      }
    };
  }, []);

  // --- Flush Cached Market Prices to UI Only When Dropdown or Home Strip Is Visible ---
  useEffect(() => {
    if (!isPairDropdownOpen && activeTab !== 'home') return;
    setMarketPrices({ ...marketPricesRef.current });
    const interval = setInterval(() => {
      setMarketPrices({ ...marketPricesRef.current });
    }, 1500);
    return () => clearInterval(interval);
  }, [isPairDropdownOpen, activeTab]);

  // --- Connect to Binance WebSocket for Selected Pair (Race-Condition Safe) ---
  useEffect(() => {
    let isCancelled = false;
    const currentSymbol = selectedPair.symbol;
    const initialPrice =
      marketPricesRef.current[currentSymbol] ||
      selectedPair.defaultPrice ||
      selectedPair.default_price ||
      '0.00';
    setLivePrice(initialPrice);
    setPriceColor('text-gray-200');

    let ws;
    try {
      const streamSymbol = currentSymbol.toLowerCase();
      ws = new WebSocket(`wss://stream.binance.com:9443/ws/${streamSymbol}@trade`);

      ws.onmessage = (event) => {
        if (isCancelled) return;
        try {
          const data = JSON.parse(event.data);
          if (!data || data.s !== currentSymbol) return;
          const rawPrice = parseFloat(data.p);
          if (isNaN(rawPrice) || rawPrice <= 0) return;
          const formatted = formatPairPrice(rawPrice);
          marketPricesRef.current[currentSymbol] = formatted;

          setLivePrice((prev) => {
            if (isCancelled) return prev;
            const prevNum = parseFloat(prev);
            if (!isNaN(prevNum)) {
              if (rawPrice > prevNum) setPriceColor('text-emerald-400');
              else if (rawPrice < prevNum) setPriceColor('text-rose-400');
            }
            return formatted;
          });
        } catch (err) {
          // Ignore malformed packet
        }
      };
    } catch (e) {
      // Fallback if WebSocket blocked
    }

    return () => {
      isCancelled = true;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
          ws.close();
        }
      }
    };
  }, [selectedPair.symbol]);

  // --- Filtered Pairs for Search ---
  const filteredPairs = useMemo(() => {
    const list = pairs || FALLBACK_PAIRS;
    const q = pairSearch.trim().toLowerCase();
    if (!q) return list.slice(0, 50);
    return list.filter((p) =>
      p.symbol?.toLowerCase().includes(q) ||
      p.label?.toLowerCase().includes(q) ||
      p.base?.toLowerCase().includes(q)
    ).slice(0, 80);
  }, [pairs, pairSearch]);

  // --- Filtered General Strategies for Search Bar ---
  const filteredGeneralStrategies = useMemo(() => {
    return defaultStrategies.filter((s) =>
      s.toLowerCase().includes(strategySearch.toLowerCase())
    );
  }, [strategySearch]);

  // --- Sync Draft Trade When Opening Detail View ---
  useEffect(() => {
    if (selectedTradeId) {
      const found = trades.find((t) => t.id === selectedTradeId);
      setDraftTrade(found ? { ...found } : null);
      setDetailSaveToast(false);
      setIsChartZoomOpen(false);
    } else {
      setDraftTrade(null);
      setIsChartZoomOpen(false);
    }
  }, [selectedTradeId]);

  // --- Check if User Modified Any Detail Field (Dirty State) ---
  const hasUnsavedChanges = useMemo(() => {
    if (!selectedTradeId || !draftTrade) return false;
    const original = trades.find((t) => t.id === selectedTradeId);
    if (!original) return false;
    return (
      original.status !== draftTrade.status ||
      original.strategy !== draftTrade.strategy ||
      original.entryReason !== draftTrade.entryReason ||
      original.notes !== draftTrade.notes ||
      original.hasChartSnapshot !== draftTrade.hasChartSnapshot ||
      original.chartTimeframe !== draftTrade.chartTimeframe ||
      original.customChartUrl !== draftTrade.customChartUrl
    );
  }, [selectedTradeId, draftTrade, trades]);

  // --- Risk Toggle & Input Handlers ---
  const handleRiskTypeToggle = (newType) => {
    if (newType === riskType) return;

    const currentBalance = parseFloat(balance) || 0;
    const currentRisk = parseFloat(riskValue) || 0;

    if (currentBalance <= 0) {
      setBalanceEmptyNotice(true);
      setRiskType(newType);
      return;
    }

    let converted = 0;
    if (newType === '$' && riskType === '%') {
      converted = currentBalance * (currentRisk / 100);
    } else if (newType === '%' && riskType === '$') {
      converted = (currentRisk / currentBalance) * 100;
    }

    setRiskValue(converted > 0 ? Number(converted.toFixed(2)).toString() : '');
    setRiskType(newType);
  };

  const handleRiskValueChange = (val) => {
    setRiskValue(val);
    const currentBalance = parseFloat(balance) || 0;
    if (currentBalance <= 0 && val !== '') {
      setBalanceEmptyNotice(true);
    } else {
      setBalanceEmptyNotice(false);
    }
  };

  const handleBalanceChange = (val) => {
    setBalance(val);
    if (parseFloat(val) > 0) {
      setBalanceEmptyNotice(false);
    }
  };

  const handleLeverageInput = (val) => {
    if (val === '') {
      setLeverage('');
      return;
    }
    const num = parseInt(val, 10);
    if (!isNaN(num)) {
      setLeverage(Math.min(2000, Math.max(1, num)));
    }
  };

  const setEntryToLivePrice = useCallback(() => {
    if (livePrice) setEntryPrice(livePrice);
  }, [livePrice]);

  // --- Step Price Helper (Starts from Live Price if empty) ---
  const adjustPriceField = (currentValue, setter, direction) => {
    const step = selectedPair.step || inferPriceStep(livePrice);
    const stepStr = step.toString();
    const decimals = stepStr.includes('.') ? stepStr.split('.')[1].length : 2;
    // decimals computed dynamically above
    const baseNum =
      currentValue !== '' && !isNaN(parseFloat(currentValue))
        ? parseFloat(currentValue)
        : parseFloat(entryPrice) || parseFloat(livePrice) || 0;

    const nextVal = Math.max(0, baseNum + direction * step);
    setter(Number(nextVal.toFixed(decimals)).toString());
  };

  const handlePriceKeyDown = (e, currentValue, setter) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      adjustPriceField(currentValue, setter, 1);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      adjustPriceField(currentValue, setter, -1);
    }
  };

  // --- Add & Delete Custom Strategy ---
  const handleAddCustomStrategy = async () => {
    const trimmed = newStrategyInput.trim();
    if (!trimmed) return;
    if (!customStrategies.includes(trimmed) && !defaultStrategies.includes(trimmed)) {
      setCustomStrategies((prev) => [trimmed, ...prev]);
      try {
        await api.createStrategy(trimmed);
      } catch (e) {
        console.warn('Failed to sync strategy creation to backend:', e);
      }
    }
    if (draftTrade) {
      setDraftTrade((prev) => ({ ...prev, strategy: trimmed }));
    }
    setNewStrategyInput('');
  };

  const handleDeleteCustomStrategy = async (stratToDelete, e) => {
    e.stopPropagation();
    setCustomStrategies((prev) => prev.filter((s) => s !== stratToDelete));
    try {
      await api.deleteStrategy(stratToDelete);
    } catch (err) {
      console.warn('Failed to delete strategy from backend:', err);
    }
    if (draftTrade && draftTrade.strategy === stratToDelete) {
      setDraftTrade((prev) => ({ ...prev, strategy: defaultStrategies[0] || 'Price Action' }));
    }
  };

  // --- Handle Custom Chart Image Upload ---
  const handleCustomChartUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !draftTrade) return;

    setIsUploadingChart(true);
    try {
      const res = await api.uploadTradeChart(draftTrade.id, file);
      if (res.chart_url || res.chartUrl) {
        const url = res.chart_url || res.chartUrl;
        updateDraftField('customChartUrl', url);
        updateDraftField('hasChartSnapshot', true);
        setTrades((prev) =>
          prev.map((t) => (t.id === draftTrade.id ? { ...t, customChartUrl: url, hasChartSnapshot: true } : t))
        );
      }
    } catch (err) {
      console.warn('Backend upload failed, reading locally as dataURL:', err);
      const reader = new FileReader();
      reader.onload = (ev) => {
        updateDraftField('customChartUrl', ev.target.result);
        updateDraftField('hasChartSnapshot', true);
      };
      reader.readAsDataURL(file);
    } finally {
      setIsUploadingChart(false);
    }
  };

  // --- Real-time Position Calculations ---
  const calcResult = useMemo(() => {
    const b = parseFloat(balance) || 0;
    const r = parseFloat(riskValue) || 0;
    const e = parseFloat(entryPrice) || 0;
    const sl = parseFloat(stopLossPrice) || 0;
    const tp = parseFloat(takeProfitPrice) || 0;
    const lev = parseFloat(leverage) || 1;
    const isLongPos = positionSide === 'LONG';

    const rAmount = riskType === '%' ? b * (r / 100) : r;
    const rPercent = b > 0 ? (riskType === '%' ? r : (r / b) * 100) : 0;

    let warningMsg = '';
    let pSize = 0;
    let rMargin = 0;
    let pValue = 0;
    let rrRatio = null;
    let potentialProfit = 0;
    let isNoSlMode = false;

    if (b <= 0) warningMsg = 'لطفاً ابتدا موجودی حساب (Balance) را وارد کنید.';
    else if (r <= 0) warningMsg = 'لطفاً مقدار ریسک مجاز را مشخص کنید.';
    else if (rAmount > b) warningMsg = 'مقدار ریسک نمی‌تواند بیشتر از کل موجودی باشد!';
    else if (e <= 0) warningMsg = 'قیمت ورود (Entry) را وارد کنید یا با فلش‌ها تنظیم نمایید.';
    else {
      if (sl > 0) {
        if (e === sl) {
          warningMsg = 'قیمت ورود و حد ضرر نمی‌توانند یکسان باشند.';
        } else if (isLongPos && sl >= e) {
          warningMsg = 'در پوزیشن Long، حد ضرر باید پایین‌تر از نقطه ورود باشد.';
        } else if (!isLongPos && sl <= e) {
          warningMsg = 'در پوزیشن Short، حد ضرر باید بالاتر از نقطه ورود باشد.';
        } else {
          const slDistanceRatio = Math.abs(e - sl) / e;
          pValue = rAmount / slDistanceRatio;
          pSize = pValue / e;
          rMargin = pValue / lev;
        }
      } else {
        isNoSlMode = true;
        rMargin = rAmount;
        pValue = rMargin * lev;
        pSize = pValue / e;
      }

      if (!warningMsg && tp > 0) {
        const validTp = isLongPos ? tp > e : tp < e;
        if (!validTp) {
          warningMsg = isLongPos
            ? 'در پوزیشن Long، حد سود باید بالاتر از نقطه ورود باشد.'
            : 'در پوزیشن Short، حد سود باید پایین‌تر از نقطه ورود باشد.';
        } else {
          potentialProfit = pSize * Math.abs(tp - e);
          if (rAmount > 0) {
            rrRatio = (potentialProfit / rAmount).toFixed(2);
          }
        }
      }

      if (!warningMsg && rMargin > b) {
        warningMsg = `مارجین مورد نیاز (${rMargin.toFixed(1)}$) از موجودی شما بیشتر است! اهرم را افزایش دهید.`;
      }
    }

    return {
      positionSize: pSize,
      requiredMargin: rMargin,
      warning: warningMsg,
      riskAmount: rAmount,
      riskPercent: rPercent,
      positionValue: pValue,
      rrRatio,
      potentialProfit,
      isNoSlMode
    };
  }, [balance, riskValue, riskType, entryPrice, stopLossPrice, takeProfitPrice, leverage, positionSide]);

  // --- Save Trade to Journal (Automatically Attaches Chart Snapshot) ---
  const handleSaveTrade = async () => {
    if (calcResult.warning || !calcResult.positionSize) return;

    const isLong = positionSide === 'LONG';
    const payload = {
      pair: selectedPair.symbol,
      is_long: isLong,
      entry_price: entryPrice,
      stop_loss: stopLossPrice || null,
      take_profit: takeProfitPrice || null,
      size: calcResult.positionSize.toFixed(4),
      margin: calcResult.requiredMargin.toFixed(2),
      leverage: leverage || 1,
      risk_amount: calcResult.riskAmount.toFixed(2),
      potential_profit: calcResult.potentialProfit > 0 ? calcResult.potentialProfit.toFixed(2) : calcResult.riskAmount.toFixed(2),
      rr: calcResult.rrRatio || '—',
      status: 'OPEN',
      strategy: defaultStrategies[0] || 'Price Action',
      entry_reason: '',
      notes: '',
      chart_timeframe: '1H'
    };

    try {
      const savedTrade = await api.createTrade(payload);
      setTrades((prev) => [savedTrade, ...prev]);
    } catch (e) {
      console.warn('Failed to save to backend, using local trade:', e);
      const localTrade = {
        id: 't_' + Date.now(),
        pair: selectedPair.label,
        base: selectedPair.base,
        isLong,
        entryPrice,
        stopLoss: stopLossPrice || '—',
        takeProfit: takeProfitPrice || '—',
        size: calcResult.positionSize.toFixed(4),
        margin: calcResult.requiredMargin.toFixed(2),
        leverage: leverage || 1,
        riskAmount: calcResult.riskAmount.toFixed(2),
        potentialProfit: calcResult.potentialProfit > 0 ? calcResult.potentialProfit.toFixed(2) : calcResult.riskAmount.toFixed(2),
        rr: calcResult.rrRatio || '—',
        status: 'OPEN',
        strategy: defaultStrategies[0] || 'Price Action',
        entryReason: '',
        notes: '',
        date: 'الان',
        hasChartSnapshot: true,
        chartTimeframe: '1H',
        customChartUrl: null
      };
      setTrades((prev) => [localTrade, ...prev]);
    }

    setSaveSuccessToast(true);
    setTimeout(() => {
      setSaveSuccessToast(false);
      setActiveTab('journal');
    }, 900);
  };

  // --- Journal Helpers ---
  const updateTradeStatus = async (id, newStatus, e) => {
    e.stopPropagation();
    try {
      const updated = await api.updateTrade(id, { status: newStatus });
      setTrades((prev) => prev.map((t) => (t.id === id ? { ...t, ...updated } : t)));
    } catch (err) {
      setTrades((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: newStatus } : t))
      );
    }
    setOpenStatusMenuId(null);
  };

  const updateDraftField = (field, value) => {
    setDraftTrade((prev) => (prev ? { ...prev, [field]: value } : null));
    setDetailSaveToast(false);
  };

  const handleSaveDraftChanges = async () => {
    if (!draftTrade) return;
    try {
      const updated = await api.updateTrade(draftTrade.id, {
        status: draftTrade.status,
        strategy: draftTrade.strategy,
        entry_reason: draftTrade.entryReason,
        notes: draftTrade.notes
      });
      setTrades((prev) =>
        prev.map((t) => (t.id === draftTrade.id ? { ...draftTrade, ...updated } : t))
      );
    } catch (err) {
      setTrades((prev) =>
        prev.map((t) => (t.id === draftTrade.id ? { ...draftTrade } : t))
      );
    }
    setDetailSaveToast(true);
    setTimeout(() => setDetailSaveToast(false), 2000);
  };

  const handleDeleteTrade = async (tradeId, e) => {
    if (e) e.stopPropagation();
    const confirmed = window.confirm('آیا از حذف این معامله از ژورنال اطمینان دارید؟');
    if (!confirmed) return;

    try {
      await api.deleteTrade(tradeId);
      setTrades((prev) => prev.filter((t) => t.id !== tradeId));
      if (selectedTradeId === tradeId) {
        setSelectedTradeId(null);
        setDraftTrade(null);
      }
    } catch (err) {
      console.warn('Failed to delete trade on backend, removing locally:', err);
      setTrades((prev) => prev.filter((t) => t.id !== tradeId));
      if (selectedTradeId === tradeId) {
        setSelectedTradeId(null);
        setDraftTrade(null);
      }
    }
  };

  const toggleInfoPopover = (key, e) => {
    e.stopPropagation();
    setActiveInfoKey((prev) => (prev === key ? null : key));
  };

  const renderInfoButton = (key, align = 'right') => {
    const info = INFO_TOOLTIPS[key];
    if (!info) return null;
    const isOpen = activeInfoKey === key;

    return (
      <div className="relative inline-flex items-center" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          onClick={(e) => toggleInfoPopover(key, e)}
          className={`w-4 h-4 sm:w-4.5 sm:h-4.5 rounded-full flex items-center justify-center text-[10px] font-serif italic font-bold transition-all ${
            isOpen
              ? 'bg-blue-500 text-white shadow-md shadow-blue-500/40 scale-110'
              : 'bg-gray-800/90 text-blue-400 hover:bg-blue-500/20 border border-gray-700'
          }`}
          title="راهنما"
        >
          i
        </button>

        {isOpen && (
          <div
            className={`absolute bottom-6 ${
              align === 'left'
                ? 'left-0'
                : align === 'center'
                ? 'left-1/2 -translate-x-1/2'
                : 'right-0'
            } w-48 sm:w-56 max-w-[calc(100vw-2rem)] bg-gray-900 border border-blue-500/40 rounded-xl p-2.5 shadow-2xl z-50 text-right`}
          >
            <div className="flex items-center justify-between border-b border-gray-800 pb-1 mb-1">
              <span className="text-[10px] sm:text-[11px] font-bold text-blue-400">{info.title}</span>
              <button
                type="button"
                onClick={(e) => toggleInfoPopover(key, e)}
                className="text-gray-500 hover:text-gray-300 text-[10px] px-1"
              >
                ✕
              </button>
            </div>
            <p className="text-[10px] sm:text-[11px] text-gray-300 leading-relaxed font-normal">
              {info.desc}
            </p>
          </div>
        )}
      </div>
    );
  };

  // --- Render Dynamic Candlestick Chart Snapshot (Simulating mplfinance Output) ---
  const renderCandlestickSnapshot = (trade, isLarge = false) => {
    if (trade.customChartUrl) {
      return (
        <div className="relative w-full overflow-hidden rounded-xl border border-gray-800 bg-gray-950">
          <img
            src={trade.customChartUrl}
            alt="Trade Chart"
            className={`w-full object-cover ${isLarge ? 'max-h-[60vh] sm:max-h-[440px]' : 'h-44 sm:h-52 md:h-60'}`}
          />
          <div className="absolute top-2 right-2 bg-gray-950/80 backdrop-blur px-2 py-0.5 rounded text-[10px] text-blue-400 border border-gray-800">
            تصویر آپلود شده توسط کاربر
          </div>
        </div>
      );
    }

    const isLongTrade = trade.isLong;
    const tpY = isLongTrade ? 28 : 132;
    const entryY = 82;
    const slY = isLongTrade ? 132 : 28;

    const candles = isLongTrade
      ? [
          { x: 18, o: 118, c: 110, h: 104, l: 124 },
          { x: 34, o: 110, c: 116, h: 106, l: 122 },
          { x: 50, o: 116, c: 102, h: 96, l: 120 },
          { x: 66, o: 102, c: 94, h: 88, l: 108 },
          { x: 82, o: 94, c: 99, h: 90, l: 105 },
          { x: 98, o: 99, c: 86, h: 80, l: 103 },
          { x: 114, o: 86, c: 82, h: 74, l: 92, isEntry: true },
          { x: 130, o: 82, c: 70, h: 64, l: 86 },
          { x: 146, o: 70, c: 75, h: 66, l: 80 },
          { x: 162, o: 75, c: 58, h: 50, l: 78 },
          { x: 178, o: 58, c: 46, h: 40, l: 62 },
          { x: 194, o: 46, c: 34, h: 26, l: 50 },
        ]
      : [
          { x: 18, o: 42, c: 50, h: 36, l: 56 },
          { x: 34, o: 50, c: 44, h: 38, l: 54 },
          { x: 50, o: 44, c: 58, h: 40, l: 64 },
          { x: 66, o: 58, c: 68, h: 54, l: 74 },
          { x: 82, o: 68, c: 62, h: 58, l: 72 },
          { x: 98, o: 62, c: 76, h: 60, l: 82 },
          { x: 114, o: 76, c: 82, h: 70, l: 88, isEntry: true },
          { x: 130, o: 82, c: 94, h: 78, l: 100 },
          { x: 146, o: 94, c: 88, h: 84, l: 98 },
          { x: 162, o: 88, c: 104, h: 86, l: 110 },
          { x: 178, o: 104, c: 116, h: 100, l: 122 },
          { x: 194, o: 116, c: 128, h: 112, l: 134 },
        ];

    return (
      <div className="relative w-full rounded-xl overflow-hidden bg-[#0b0f19] border border-gray-800">
        {/* Top Watermark Bar inside Chart */}
        <div dir="ltr" className="flex flex-wrap items-center justify-between gap-1 px-3 py-1.5 bg-gray-950/80 border-b border-gray-800/80 text-[9px] sm:text-[10px] font-mono">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <span className="font-bold text-white">{trade.pair}</span>
            <span className="bg-blue-500/20 text-blue-400 px-1.5 py-0.2 rounded border border-blue-500/30">
              {trade.chartTimeframe || '1H'}
            </span>
            <span className="text-gray-500 hidden xs:inline">mplfinance • Auto-Snapshot</span>
          </div>
          <span className="text-gray-400">{trade.date}</span>
        </div>

        {/* SVG Candlestick & Levels Canvas */}
        <svg
          viewBox="0 0 280 160"
          className={`w-full block ${isLarge ? 'h-56 sm:h-72 md:h-80' : 'h-40 sm:h-48 md:h-56'}`}
          preserveAspectRatio="none"
        >
          {/* Subtle Grid Lines */}
          {[30, 65, 100, 135].map((gy) => (
            <line key={gy} x1="0" y1={gy} x2="280" y2={gy} stroke="#1e293b" strokeWidth="0.6" strokeDasharray="2 2" />
          ))}
          {[50, 110, 170, 230].map((gx) => (
            <line key={gx} x1={gx} y1="0" x2={gx} y2="160" stroke="#1e293b" strokeWidth="0.6" strokeDasharray="2 2" />
          ))}

          {/* Shaded Profit / Loss Zones from Entry Candle */}
          {trade.takeProfit !== '—' && (
            <rect
              x="114"
              y={Math.min(entryY, tpY)}
              width="105"
              height={Math.abs(entryY - tpY)}
              fill="#10b981"
              fillOpacity="0.09"
            />
          )}
          {trade.stopLoss !== '—' && (
            <rect
              x="114"
              y={Math.min(entryY, slY)}
              width="105"
              height={Math.abs(entryY - slY)}
              fill="#f43f5e"
              fillOpacity="0.09"
            />
          )}

          {/* Take Profit Line */}
          {trade.takeProfit !== '—' && (
            <g>
              <line x1="8" y1={tpY} x2="222" y2={tpY} stroke="#10b981" strokeWidth="1" strokeDasharray="4 3" />
              <rect x="222" y={tpY - 8} width="54" height="16" rx="3" fill="#064e3b" stroke="#10b981" strokeWidth="0.7" />
              <text x="249" y={tpY + 3} fill="#34d399" fontSize="7.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
                TP {trade.takeProfit}
              </text>
            </g>
          )}

          {/* Entry Line */}
          <g>
            <line x1="8" y1={entryY} x2="222" y2={entryY} stroke="#3b82f6" strokeWidth="1.1" />
            <rect x="222" y={entryY - 8} width="54" height="16" rx="3" fill="#1e3a8a" stroke="#3b82f6" strokeWidth="0.7" />
            <text x="249" y={entryY + 3} fill="#93c5fd" fontSize="7.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
              EN {trade.entryPrice}
            </text>
          </g>

          {/* Stop Loss Line */}
          {trade.stopLoss !== '—' && (
            <g>
              <line x1="8" y1={slY} x2="222" y2={slY} stroke="#f43f5e" strokeWidth="1" strokeDasharray="4 3" />
              <rect x="222" y={slY - 8} width="54" height="16" rx="3" fill="#881337" stroke="#f43f5e" strokeWidth="0.7" />
              <text x="249" y={slY + 3} fill="#fda4af" fontSize="7.5" fontFamily="monospace" textAnchor="middle" fontWeight="bold">
                SL {trade.stopLoss}
              </text>
            </g>
          )}

          {/* Candlesticks */}
          {candles.map((c, idx) => {
            const bullish = c.c <= c.o;
            const color = bullish ? '#10b981' : '#f43f5e';
            const bodyTop = Math.min(c.o, c.c);
            const bodyHeight = Math.max(2.5, Math.abs(c.c - c.o));
            return (
              <g key={idx}>
                <line x1={c.x} y1={c.h} x2={c.x} y2={c.l} stroke={color} strokeWidth="1.2" />
                <rect x={c.x - 4} y={bodyTop} width="8" height={bodyHeight} rx="1" fill={color} />
                {c.isEntry && (
                  <circle cx={c.x} cy={entryY} r="3.2" fill="#3b82f6" stroke="#ffffff" strokeWidth="1" />
                )}
              </g>
            );
          })}
        </svg>
      </div>
    );
  };

  const journalStats = useMemo(() => {
    const closed = trades.filter((t) => t.status === 'TP' || t.status === 'SL' || t.status === 'DRAW');
    const wins = trades.filter((t) => t.status === 'TP').length;
    const losses = trades.filter((t) => t.status === 'SL').length;
    const openTrades = trades.filter((t) => t.status === 'OPEN');
    const decisiveClosed = wins + losses;
    const winRate = decisiveClosed > 0 ? Math.round((wins / decisiveClosed) * 100) : 0;

    let netPnL = 0;
    let totalProfit = 0;
    let totalLoss = 0;

    trades.forEach((t) => {
      if (t.status === 'TP') {
        const p = parseFloat(t.potentialProfit || t.riskAmount) || 0;
        netPnL += p;
        totalProfit += p;
      } else if (t.status === 'SL') {
        const l = parseFloat(t.riskAmount) || 0;
        netPnL -= l;
        totalLoss += l;
      }
    });

    const openMargin = openTrades.reduce((acc, t) => acc + (parseFloat(t.margin) || 0), 0);
    const openRisk = openTrades.reduce((acc, t) => acc + (parseFloat(t.riskAmount) || 0), 0);

    // Strategy Breakdown
    const stratMap = {};
    trades.forEach((t) => {
      const s = t.strategy || 'سایر';
      if (!stratMap[s]) stratMap[s] = { name: s, total: 0, wins: 0, pnl: 0 };
      stratMap[s].total += 1;
      if (t.status === 'TP') {
        stratMap[s].wins += 1;
        stratMap[s].pnl += parseFloat(t.potentialProfit || t.riskAmount) || 0;
      } else if (t.status === 'SL') {
        stratMap[s].pnl -= parseFloat(t.riskAmount) || 0;
      }
    });

    const strategiesList = Object.values(stratMap).sort((a, b) => b.pnl - a.pnl);
    const bestStrategy = strategiesList.length > 0 ? strategiesList[0].name : '—';

    const baseBal = parseFloat(balance) || 1000;
    const currentEquity = baseBal + netPnL;
    const pnlPercent = baseBal > 0 ? (netPnL / baseBal) * 100 : 0;

    return {
      total: trades.length,
      wins,
      losses,
      openCount: openTrades.length,
      closedCount: closed.length,
      winRate,
      netPnL,
      totalProfit,
      totalLoss,
      openMargin,
      openRisk,
      currentEquity,
      pnlPercent,
      strategiesList,
      bestStrategy
    };
  }, [trades, balance]);

  const isLong = positionSide === 'LONG';

  // Helper to get trade result display info
  const getTradeResultMeta = (trade) => {
    if (trade.status === 'TP') {
      const profit = trade.potentialProfit || trade.riskAmount;
      return {
        badge: 'TP (برنده)',
        pnlText: `+$${profit}`,
        color: 'text-emerald-400',
        bg: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
      };
    }
    if (trade.status === 'SL') {
      return {
        badge: 'SL (بازنده)',
        pnlText: `-$${trade.riskAmount}`,
        color: 'text-rose-400',
        bg: 'bg-rose-500/15 border-rose-500/30 text-rose-400'
      };
    }
    if (trade.status === 'DRAW') {
      return {
        badge: 'Draw (سربه‌سر)',
        pnlText: '$0.00',
        color: 'text-amber-400',
        bg: 'bg-amber-500/15 border-amber-500/30 text-amber-400'
      };
    }
    return {
      badge: 'باز (در جریان)',
      pnlText: 'در انتظار نتیجه',
      color: 'text-blue-400',
      bg: 'bg-blue-500/15 border-blue-500/30 text-blue-400'
    };
  };

  return (
    <div
      dir="rtl"
      onClick={() => setActiveInfoKey(null)}
      style={{ height: 'var(--tg-viewport-height, 100dvh)' }} className="h-[100dvh] w-full bg-slate-950 text-gray-200 font-sans flex justify-center items-center p-0 select-none overflow-hidden"
    >
      {/* Global CSS Reset for Number Input Spinners & Custom Scrollbars */}
      <style>{`
        input[type="number"]::-webkit-inner-spin-button,
        input[type="number"]::-webkit-outer-spin-button {
          -webkit-appearance: none;
          margin: 0;
        }
        input[type="number"] {
          -moz-appearance: textfield;
          appearance: textfield;
        }
        .no-scrollbar::-webkit-scrollbar {
          display: none;
        }
        .no-scrollbar {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>

      {/* Responsive App Shell: Full-height pinned dock on mobile & Telegram Desktop */}
      <div style={{ paddingTop: 'calc(var(--tg-safe-area-inset-top, 0px) + var(--tg-content-safe-area-inset-top, 0px))' }} className="w-full h-full max-w-full sm:max-w-xl md:max-w-3xl lg:max-w-4xl bg-gray-900 sm:border-x border-gray-800/80 shadow-2xl overflow-hidden flex flex-col relative">
        
        {/* ==================== TAB 0: HOME DASHBOARD (صفحه اصلی) ==================== */}
        {activeTab === 'home' && (
          <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 sm:space-y-5 pb-6">
            {/* Top Welcome Header */}
            <div className="flex items-center justify-between gap-2 bg-gray-950/70 p-3 sm:p-4 rounded-2xl border border-gray-800/80">
              <div className="flex items-center gap-2.5 sm:gap-3.5 min-w-0">
                <div className="relative shrink-0">
                  {userPhoto ? (
                    <img
                      src={userPhoto}
                      alt={userName}
                      className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl object-cover border border-gray-700/80 shadow-lg shadow-blue-500/10"
                      onError={() => setUserPhoto(null)}
                    />
                  ) : (
                    <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-500 to-purple-500 flex items-center justify-center text-white font-extrabold text-sm sm:text-base shadow-lg shadow-blue-500/20">
                      {(userName || 'U').charAt(0)}
                    </div>
                  )}
                  <span className="w-2.5 h-2.5 sm:w-3 sm:h-3 rounded-full bg-emerald-500 border-2 border-gray-950 absolute -bottom-0.5 -right-0.5"></span>
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="text-[11px] sm:text-xs text-gray-400">خوش آمدی،</span>
                    <span className="text-xs sm:text-sm font-extrabold text-white truncate max-w-full">{userName} عزیز 👋</span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    <span className="text-[9px] sm:text-[10px] bg-blue-500/15 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full font-medium whitespace-nowrap">
                      سطح انضباط: حرفه‌ای 🛡️
                    </span>
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={() => setActiveTab('calc')}
                className="shrink-0 whitespace-nowrap bg-blue-600/15 hover:bg-blue-600/25 border border-blue-500/30 text-blue-400 px-2.5 sm:px-3.5 py-2 sm:py-2.5 rounded-xl text-[10px] sm:text-xs font-bold flex items-center gap-1 transition-all active:scale-95"
              >
                <span>+ ترید جدید</span>
              </button>
            </div>

            {/* Hero Portfolio & Balance Card */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-950/90 via-slate-900 to-gray-950 border border-blue-500/30 p-3.5 sm:p-5 shadow-xl">
              <div className="absolute -left-10 -top-10 w-36 h-36 bg-blue-500/10 rounded-full blur-2xl pointer-events-none"></div>
              <div className="absolute -right-8 -bottom-8 w-28 h-28 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none"></div>

              <div className="flex flex-wrap justify-between items-start gap-2 relative z-10">
                <div>
                  <span className="text-[11px] sm:text-xs text-blue-300/80 flex items-center gap-1.5">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></svg>
                    ارزش کل پورتفولیو (Equity)
                  </span>
                  <div dir="ltr" className="text-right mt-1 flex items-baseline justify-end gap-1.5">
                    <span className="font-mono text-xl sm:text-2xl md:text-3xl font-extrabold text-white tracking-tight">
                      ${journalStats.currentEquity.toFixed(2)}
                    </span>
                    <span className="text-[10px] sm:text-xs font-mono text-gray-400">USDT</span>
                  </div>
                </div>

                <div className="text-left">
                  <span className="text-[10px] sm:text-xs text-gray-400 block">سود / زیان خالص</span>
                  <div
                    dir="ltr"
                    className={`mt-1 inline-flex items-center gap-1 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-lg text-xs sm:text-sm font-mono font-bold border ${
                      journalStats.netPnL >= 0
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    <span>{journalStats.netPnL >= 0 ? `+${journalStats.netPnL.toFixed(2)}$` : `-${Math.abs(journalStats.netPnL).toFixed(2)}$`}</span>
                    <span className="text-[10px] sm:text-xs opacity-80">({journalStats.pnlPercent >= 0 ? '+' : ''}{journalStats.pnlPercent.toFixed(1)}%)</span>
                  </div>
                </div>
              </div>

              {/* 4 Mini Metrics Inside Hero Card - Responsive 2x2 on tiny screens, 4 cols on standard/desktop */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mt-4 pt-3 border-t border-gray-800/80 relative z-10 text-center">
                <div className="bg-gray-950/60 rounded-xl p-2 sm:p-2.5 border border-gray-800/60">
                  <span className="text-[9px] sm:text-[10px] text-gray-400 block">وین‌ریت</span>
                  <span className="font-mono text-xs sm:text-sm font-bold text-emerald-400 mt-0.5 block">{journalStats.winRate}%</span>
                </div>
                <div className="bg-gray-950/60 rounded-xl p-2 sm:p-2.5 border border-gray-800/60">
                  <span className="text-[9px] sm:text-[10px] text-gray-400 block">پوزیشن باز</span>
                  <span className="font-mono text-xs sm:text-sm font-bold text-blue-400 mt-0.5 block">{journalStats.openCount}</span>
                </div>
                <div className="bg-gray-950/60 rounded-xl p-2 sm:p-2.5 border border-gray-800/60">
                  <span className="text-[9px] sm:text-[10px] text-gray-400 block">مارجین درگیر</span>
                  <span dir="ltr" className="font-mono text-xs sm:text-sm font-bold text-gray-200 mt-0.5 block">${journalStats.openMargin.toFixed(0)}</span>
                </div>
                <div className="bg-gray-950/60 rounded-xl p-2 sm:p-2.5 border border-gray-800/60">
                  <span className="text-[9px] sm:text-[10px] text-gray-400 block">ریسک فعال</span>
                  <span dir="ltr" className="font-mono text-xs sm:text-sm font-bold text-amber-400 mt-0.5 block">${journalStats.openRisk.toFixed(0)}</span>
                </div>
              </div>
            </div>

            {/* Live Market Ticker Strip */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center px-1">
                <span className="text-[11px] sm:text-xs font-bold text-gray-300 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
                  نبض لحظه‌ای بازار
                </span>
                <span className="text-[9px] sm:text-[10px] text-gray-500">بکشید یا برای محاسبه کلیک کنید</span>
              </div>
              <div
                ref={tickerRef}
                onMouseDown={handleTickerMouseDown}
                onMouseMove={handleTickerMouseMove}
                onMouseUp={handleTickerMouseUpOrLeave}
                onMouseLeave={handleTickerMouseUpOrLeave}
                className="flex gap-2 sm:gap-2.5 overflow-x-auto pb-1 no-scrollbar cursor-grab active:cursor-grabbing select-none"
              >
                {pairs.slice(0, 15).map((pair) => {
                  const isCurrent = selectedPair.symbol === pair.symbol;
                  const displayPrice = isCurrent ? livePrice : (marketPrices[pair.symbol] || pair.defaultPrice);
                  return (
                    <button
                      key={pair.symbol}
                      type="button"
                      onClick={() => {
                        if (hasDraggedRef.current) return;
                        setSelectedPair(pair);
                        setActiveTab('calc');
                      }}
                      className="shrink-0 bg-gray-950 hover:bg-gray-900 border border-gray-800 hover:border-blue-500/40 rounded-xl px-3 sm:px-3.5 py-2 sm:py-2.5 flex items-center gap-2 transition-all"
                    >
                      <span className={`w-6 h-6 sm:w-7 sm:h-7 rounded-lg flex items-center justify-center text-xs sm:text-sm font-bold ${pair.color}`}>
                        {pair.icon}
                      </span>
                      <div className="text-right">
                        <span className="text-[10px] sm:text-xs font-bold text-white block">{pair.base}/USDT</span>
                        <span dir="ltr" className="text-[10px] sm:text-[11px] font-mono text-gray-400 block">${displayPrice}</span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Active Strategy Spotlight */}
            <div
              onClick={() => setActiveTab('portfolio')}
              className="bg-gradient-to-l from-purple-950/30 via-gray-950 to-gray-950 border border-purple-500/25 rounded-2xl p-3 sm:p-4 flex items-center justify-between gap-2 cursor-pointer hover:border-purple-500/50 transition-all"
            >
              <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-1">
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
                </div>
                <div>
                  <span className="text-[10px] sm:text-xs text-gray-400 block">بهترین استراتژی ثبت‌شده شما</span>
                  <span className="text-xs sm:text-sm font-bold text-white block truncate">{journalStats.bestStrategy}</span>
                </div>
              </div>
              <div className="flex items-center gap-1 text-[10px] sm:text-xs text-purple-400 font-bold shrink-0">
                <span>آمار پورتفولیو</span>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
              </div>
            </div>

            {/* Recent & Open Trades Summary */}
            <div className="space-y-2.5">
              <div className="flex justify-between items-center px-1">
                <h3 className="text-xs sm:text-sm font-bold text-gray-200">خلاصه آخرین معاملات شما</h3>
                <button
                  type="button"
                  onClick={() => setActiveTab('journal')}
                  className="text-[10px] sm:text-xs text-blue-400 hover:text-blue-300 font-bold flex items-center gap-0.5"
                >
                  مشاهده همه ({trades.length})
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 sm:gap-3">
                {trades.length === 0 ? (
                  <div className="col-span-full bg-gray-950/60 border border-dashed border-gray-800 rounded-xl p-4 text-center">
                    <span className="text-gray-500 text-xs block">هنوز معامله‌ای در ژورنال ثبت نشده است.</span>
                    <button
                      type="button"
                      onClick={() => setActiveTab('calc')}
                      className="text-[11px] text-blue-400 font-bold mt-1.5 hover:underline"
                    >
                      ثبت اولین معامله با ماشین‌حساب ←
                    </button>
                  </div>
                ) : (
                  trades.slice(0, 4).map((trade) => {
                  const meta = getTradeResultMeta(trade);
                  return (
                    <div
                      key={trade.id}
                      onClick={() => {
                        setSelectedTradeId(trade.id);
                        setActiveTab('journal');
                      }}
                      className="bg-gray-950 hover:bg-gray-900 border border-gray-800/90 rounded-xl p-3 sm:p-3.5 flex items-center justify-between gap-2 cursor-pointer transition-all"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className={`w-8 h-8 sm:w-9 sm:h-9 shrink-0 rounded-lg flex items-center justify-center text-[10px] sm:text-xs font-mono font-extrabold ${
                          trade.isLong ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                        }`}>
                          {trade.isLong ? 'L' : 'S'}
                        </span>
                        <div className="min-w-0">
                          <div className="text-xs sm:text-sm font-bold text-white flex flex-wrap items-center gap-1.5">
                            <span>{trade.pair}</span>
                            <span className="text-[9px] sm:text-[10px] font-mono bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">{trade.leverage}x</span>
                            {trade.hasChartSnapshot && (
                              <span className="text-[9px] bg-blue-500/15 text-blue-400 px-1.5 py-0.5 rounded">📊 چارت</span>
                            )}
                          </div>
                          <span className="text-[10px] sm:text-[11px] text-gray-500 block mt-0.5 truncate">
                            {trade.strategy} • ورود: <span className="font-mono text-gray-400">${trade.entryPrice}</span>
                          </span>
                        </div>
                      </div>

                      <div className="text-left shrink-0">
                        <span dir="ltr" className={`font-mono text-xs sm:text-sm font-bold block ${meta.color}`}>
                          {meta.pnlText}
                        </span>
                        <span className="text-[9px] sm:text-[10px] text-gray-500 block mt-0.5">{meta.badge}</span>
                      </div>
                    </div>
                  );
                })
              )}
              </div>
            </div>
          </div>
        )}

        {/* ==================== TAB 1: RISK CALCULATOR ==================== */}
        {activeTab === 'calc' && (
          <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
            {/* Pair Selector & Live Price Header */}
            <div className="shrink-0 bg-gray-950/90 px-3.5 sm:px-5 py-3 sm:py-3.5 border-b border-gray-800 flex justify-between items-center gap-2 relative z-20">
              <div className="relative">
                <button
                  onClick={() => setIsPairDropdownOpen(!isPairDropdownOpen)}
                  className="flex items-center gap-2 sm:gap-2.5 bg-gray-900 hover:bg-gray-800 border border-gray-700/80 px-2.5 sm:px-3.5 py-2 rounded-xl transition-colors"
                >
                  <div className={`w-7 h-7 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center font-bold text-sm ${selectedPair.color}`}>
                    {selectedPair.icon}
                  </div>
                  <div className="text-right">
                    <div className="text-xs sm:text-sm font-bold text-white flex items-center gap-1.5">
                      {selectedPair.label}
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`transition-transform ${isPairDropdownOpen ? 'rotate-180' : ''}`}><polyline points="6 9 12 15 18 9"/></svg>
                    </div>
                    <span className="text-[10px] text-gray-400 block">Perpetual</span>
                  </div>
                </button>

                {/* Searchable Pair Dropdown */}
                {isPairDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-60 sm:w-64 max-w-[calc(100vw-2rem)] bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-2 z-30">
                    <div className="relative mb-2">
                      <input
                        type="text"
                        value={pairSearch}
                        onChange={(e) => setPairSearch(e.target.value)}
                        placeholder="جستجوی ارز (مثلاً BTC)..."
                        className="w-full bg-gray-950 border border-gray-700 rounded-lg pr-8 pl-3 py-1.5 text-xs text-white outline-none focus:border-blue-500"
                        autoFocus
                      />
                      <svg width="13" height="13" className="text-gray-500 absolute right-2.5 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    </div>
                    <div className="max-h-48 overflow-y-auto space-y-1">
                      {pairsLoading && pairs.length <= FALLBACK_PAIRS.length && (
                        <div className="text-[10px] text-gray-500 text-center py-1">در حال دریافت جفت‌ارزهای بازار...</div>
                      )}
                      {filteredPairs.length === 0 ? (
                        <div className="text-xs text-gray-500 text-center py-4">جفت‌ارزی با این نام یافت نشد</div>
                      ) : filteredPairs.map((pair) => {
                        const rowPrice = pair.symbol === selectedPair.symbol ? livePrice : (marketPrices[pair.symbol] || pair.defaultPrice);
                        return (
                        <button
                          key={pair.symbol}
                          onClick={() => {
                            setSelectedPair(pair);
                            setEntryPrice('');
                            setStopLossPrice('');
                            setTakeProfitPrice('');
                            setIsPairDropdownOpen(false);
                            setPairSearch('');
                          }}
                          className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs transition-colors ${
                            selectedPair.symbol === pair.symbol ? 'bg-blue-600/20 text-blue-400 font-bold' : 'hover:bg-gray-800 text-gray-300'
                          }`}
                        >
                          <span className="flex items-center gap-2">
                            <span className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold shrink-0 ${pair.color}`}>{pair.icon}</span>
                            {pair.label}
                          </span>
                          <span dir="ltr" className="font-mono text-[11px] text-gray-300">${rowPrice}</span>
                        </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <div className="text-left">
                <div className="flex items-center justify-end gap-1.5 text-[10px] sm:text-xs text-gray-400 mb-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                  قیمت لحظه‌ای
                </div>
                <div dir="ltr" className={`font-mono text-base sm:text-xl font-bold tracking-tight transition-colors duration-300 ${priceColor}`}>
                  ${livePrice}
                </div>
              </div>
            </div>

            {/* Calculator Form Body */}
            <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 pb-6">
              
              {/* Long / Short Direction Toggle */}
              <div className="grid grid-cols-2 gap-2 bg-gray-950 p-1.5 rounded-xl border border-gray-800">
                <button
                  type="button"
                  onClick={() => setPositionSide('LONG')}
                  className={`py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-bold flex items-center justify-center gap-1.5 transition-all ${
                    positionSide === 'LONG'
                      ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-900/40'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <span>▲</span> Long (خرید)
                </button>
                <button
                  type="button"
                  onClick={() => setPositionSide('SHORT')}
                  className={`py-2 sm:py-2.5 rounded-lg text-xs sm:text-sm font-bold flex items-center justify-center gap-1.5 transition-all ${
                    positionSide === 'SHORT'
                      ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/40'
                      : 'text-gray-400 hover:text-gray-200'
                  }`}
                >
                  <span>▼</span> Short (فروش)
                </button>
              </div>

              {/* Balance + Risk Row (Stacks on very narrow screens <360px, 2 columns on standard mobile & up) */}
              <div className="grid grid-cols-1 min-[360px]:grid-cols-2 gap-3 sm:gap-4">
                {/* Balance Input */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-gray-400 flex items-center gap-1.5 h-6">
                    <svg width="13" height="13" className="text-blue-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4Z"/></svg>
                    <span className="truncate">موجودی (Balance)</span>
                  </label>
                  <div className="relative">
                    <input
                      dir="ltr"
                      type="number"
                      value={balance}
                      onChange={(e) => handleBalanceChange(e.target.value)}
                      placeholder="1000"
                      className={`w-full bg-gray-950 border rounded-xl pl-3 pr-12 py-2.5 text-white outline-none transition-colors font-mono text-sm ${
                        balanceEmptyNotice ? 'border-amber-500 ring-1 ring-amber-500/30' : 'border-gray-700 focus:border-blue-500'
                      }`}
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 font-mono text-[11px]">USDT</span>
                  </div>

                  {/* Envelope-style Inline Notification under Balance */}
                  {balanceEmptyNotice && (
                    <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-2 flex items-center gap-2 animate-pulse">
                      <svg width="13" height="13" className="text-amber-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>
                      <span className="text-[10px] text-amber-300 leading-tight">
                        این بخش خالی است! ابتدا موجودی را وارد کنید.
                      </span>
                    </div>
                  )}
                </div>

                {/* Risk Input with % / $ Small Top Buttons */}
                <div className="space-y-1.5">
                  <div className="flex justify-between items-center gap-1 h-6">
                    <label className="text-xs font-medium text-gray-400 flex items-center gap-1">
                      مقدار ریسک
                      {renderInfoButton('risk', 'center')}
                    </label>
                    <div className="flex bg-gray-950 p-0.5 rounded-lg border border-gray-800 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleRiskTypeToggle('%')}
                        className={`px-2 py-0.5 rounded-md text-[11px] font-bold transition-all ${
                          riskType === '%' ? 'bg-blue-600 text-white shadow' : 'text-gray-500 hover:text-gray-300'
                        }`}
                      >
                        %
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRiskTypeToggle('$')}
                        className={`px-2 py-0.5 rounded-md text-[11px] font-bold transition-all ${
                          riskType === '$' ? 'bg-blue-600 text-white shadow' : 'text-gray-500 hover:text-gray-300'
                        }`}
                      >
                        $
                      </button>
                    </div>
                  </div>
                  <div className="relative">
                    <input
                      dir="ltr"
                      type="number"
                      step="any"
                      value={riskValue}
                      onChange={(e) => handleRiskValueChange(e.target.value)}
                      placeholder={riskType === '%' ? '2' : '20'}
                      className="w-full bg-gray-950 border border-gray-700 rounded-xl pl-3 pr-9 py-2.5 text-white focus:border-blue-500 outline-none transition-colors font-mono text-sm"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 font-mono text-xs">
                      {riskType}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-500 font-mono text-left" dir="ltr">
                    {riskType === '%'
                      ? `≈ $${calcResult.riskAmount.toFixed(2)} USDT`
                      : `≈ ${calcResult.riskPercent.toFixed(1)}% of Balance`}
                  </div>
                </div>
              </div>

              {/* Leverage Input (1 to 2000) + Quick Slider */}
              <div className="bg-gray-950 p-3 sm:p-4 rounded-xl border border-gray-800 space-y-2.5">
                <div className="flex justify-between items-center gap-2">
                  <label className="text-xs font-medium text-gray-400 flex items-center gap-1.5 min-w-0">
                    <span>اهرم معاملاتی (1x - 2000x)</span>
                    {renderInfoButton('leverage', 'right')}
                  </label>
                  <div className="relative flex items-center shrink-0">
                    <input
                      dir="ltr"
                      type="number"
                      min="1"
                      max="2000"
                      value={leverage}
                      onChange={(e) => handleLeverageInput(e.target.value)}
                      className="w-16 sm:w-20 bg-gray-900 border border-gray-700 focus:border-blue-500 rounded-lg pl-2 pr-5 py-1 text-center font-mono text-xs font-bold text-blue-400 outline-none"
                    />
                    <span className="absolute right-2 text-[11px] font-mono text-gray-500">x</span>
                  </div>
                </div>
                <input
                  type="range"
                  min="1"
                  max="200"
                  value={Math.min(200, leverage || 1)}
                  onChange={(e) => setLeverage(parseInt(e.target.value, 10))}
                  className="w-full accent-blue-500 bg-gray-800 h-1.5 rounded-lg cursor-pointer"
                />
                {/* Responsive 4-col on narrow mobile, 8-col on larger screens */}
                <div className="grid grid-cols-4 sm:grid-cols-8 gap-1.5">
                  {[1, 5, 10, 25, 50, 100, 500, 1000].map((lev) => (
                    <button
                      key={lev}
                      type="button"
                      onClick={() => setLeverage(lev)}
                      className={`py-1.5 rounded-lg text-[10px] sm:text-[11px] font-mono transition-colors ${
                        Number(leverage) === lev
                          ? 'bg-blue-600/30 text-blue-300 border border-blue-500/40 font-bold'
                          : 'bg-gray-900 text-gray-500 hover:text-gray-300'
                      }`}
                    >
                      {lev}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Entry, Stop Loss (Optional), Take Profit (Optional) with Live-Price Steppers */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 sm:gap-3">
                {/* Entry Price */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] sm:text-xs font-medium text-gray-400">نقطه ورود</label>
                    <button
                      type="button"
                      onClick={setEntryToLivePrice}
                      className="bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-[9px] sm:text-[10px] px-1.5 py-0.5 rounded font-bold transition-colors"
                    >
                      LIVE
                    </button>
                  </div>
                  <div className="relative flex items-center bg-gray-950 border border-gray-700 rounded-xl focus-within:border-blue-500 overflow-hidden">
                    <input
                      dir="ltr"
                      type="number"
                      step="any"
                      value={entryPrice}
                      onChange={(e) => setEntryPrice(e.target.value)}
                      onKeyDown={(e) => handlePriceKeyDown(e, entryPrice, setEntryPrice)}
                      placeholder={livePrice}
                      className="w-full bg-transparent pl-3 pr-7 py-2.5 text-white outline-none font-mono text-xs sm:text-sm"
                    />
                    <div className="absolute right-0 inset-y-0 w-6 flex flex-col border-l border-gray-800 bg-gray-900/80">
                      <button
                        type="button"
                        onClick={() => adjustPriceField(entryPrice, setEntryPrice, 1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-white hover:bg-gray-800"
                        title="افزایش از قیمت فعلی"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => adjustPriceField(entryPrice, setEntryPrice, -1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-white hover:bg-gray-800 border-t border-gray-800"
                        title="کاهش از قیمت فعلی"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                </div>

                {/* Stop Loss (Optional) */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] sm:text-xs font-medium text-rose-400">حد ضرر (SL)</label>
                    <span className="text-[9px] sm:text-[10px] text-gray-500">اختیاری</span>
                  </div>
                  <div className="relative flex items-center bg-gray-950 border border-gray-700 rounded-xl focus-within:border-rose-500 overflow-hidden">
                    <input
                      dir="ltr"
                      type="number"
                      step="any"
                      value={stopLossPrice}
                      onChange={(e) => setStopLossPrice(e.target.value)}
                      onKeyDown={(e) => handlePriceKeyDown(e, stopLossPrice, setStopLossPrice)}
                      placeholder="اختیاری"
                      className="w-full bg-transparent pl-3 pr-7 py-2.5 text-white outline-none font-mono text-xs sm:text-sm"
                    />
                    <div className="absolute right-0 inset-y-0 w-6 flex flex-col border-l border-gray-800 bg-gray-900/80">
                      <button
                        type="button"
                        onClick={() => adjustPriceField(stopLossPrice, setStopLossPrice, 1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-rose-400 hover:bg-gray-800"
                        title="افزایش از قیمت فعلی"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => adjustPriceField(stopLossPrice, setStopLossPrice, -1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-rose-400 hover:bg-gray-800 border-t border-gray-800"
                        title="کاهش از قیمت فعلی"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                </div>

                {/* Take Profit (Optional) */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] sm:text-xs font-medium text-emerald-400">حد سود (TP)</label>
                    <span className="text-[9px] sm:text-[10px] text-gray-500">اختیاری</span>
                  </div>
                  <div className="relative flex items-center bg-gray-950 border border-gray-700 rounded-xl focus-within:border-emerald-500 overflow-hidden">
                    <input
                      dir="ltr"
                      type="number"
                      step="any"
                      value={takeProfitPrice}
                      onChange={(e) => setTakeProfitPrice(e.target.value)}
                      onKeyDown={(e) => handlePriceKeyDown(e, takeProfitPrice, setTakeProfitPrice)}
                      placeholder="اختیاری"
                      className="w-full bg-transparent pl-3 pr-7 py-2.5 text-white outline-none font-mono text-xs sm:text-sm"
                    />
                    <div className="absolute right-0 inset-y-0 w-6 flex flex-col border-l border-gray-800 bg-gray-900/80">
                      <button
                        type="button"
                        onClick={() => adjustPriceField(takeProfitPrice, setTakeProfitPrice, 1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-emerald-400 hover:bg-gray-800"
                        title="افزایش از قیمت فعلی"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => adjustPriceField(takeProfitPrice, setTakeProfitPrice, -1)}
                        className="flex-1 flex items-center justify-center text-[8px] text-gray-400 hover:text-emerald-400 hover:bg-gray-800 border-t border-gray-800"
                        title="کاهش از قیمت فعلی"
                      >
                        ▼
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Validation Warning Banner */}
              {calcResult.warning && (
                <div className="bg-rose-500/10 border border-rose-500/25 rounded-xl p-3 flex items-center gap-2.5">
                  <svg width="16" height="16" className="text-rose-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <p className="text-rose-300 text-xs">{calcResult.warning}</p>
                </div>
              )}

              {/* Live Calculation Output Box */}
              <div className="bg-gray-950 rounded-xl p-3.5 sm:p-4 border border-gray-800 space-y-3 relative">
                <div className="flex flex-wrap justify-between items-center gap-2 border-b border-gray-800/80 pb-2.5">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs sm:text-sm font-bold text-gray-400">نتیجه محاسبات لحظه‌ای</span>
                    {calcResult.isNoSlMode && !calcResult.warning && (
                      <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                        بدون SL (بر اساس مارجین)
                      </span>
                    )}
                  </div>
                  <span className={`px-2.5 py-0.5 rounded-md text-[11px] font-bold font-mono ${
                    isLong ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                  }`}>
                    {isLong ? '▲ LONG' : '▼ SHORT'}
                  </span>
                </div>

                {/* Independent Top Row: Required Margin */}
                <div className="bg-gradient-to-l from-blue-950/40 via-gray-900 to-gray-900 p-3 sm:p-4 rounded-xl border border-blue-500/30 flex items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1.5 text-gray-300 text-xs sm:text-sm font-bold">
                      <span>مارجین درگیر (Margin)</span>
                      {renderInfoButton('margin', 'right')}
                    </div>
                    <span className="text-[10px] sm:text-xs text-gray-500 block">سرمایه درگیر از بالانس شما</span>
                  </div>
                  <div dir="ltr" className="text-left shrink-0">
                    <span className="font-mono text-lg sm:text-2xl text-blue-400 font-extrabold tracking-tight">
                      {calcResult.warning || !calcResult.requiredMargin ? '0.00' : calcResult.requiredMargin.toFixed(2)}
                    </span>
                    <span className="text-xs font-mono text-gray-400 ml-1">USDT</span>
                  </div>
                </div>

                {/* Compact 3-Column Row Underneath */}
                <div className="grid grid-cols-3 gap-1.5 sm:gap-3">
                  {/* Position Size */}
                  <div className="bg-gray-900/80 p-2 sm:p-3 rounded-xl border border-gray-800/70 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-gray-400 text-[10px] sm:text-xs mb-1">
                      <span className="truncate">حجم ({selectedPair.base})</span>
                      {renderInfoButton('size', 'right')}
                    </div>
                    <p dir="ltr" className="font-mono text-xs sm:text-sm text-white font-bold text-left truncate">
                      {calcResult.warning || !calcResult.positionSize ? '0.0000' : calcResult.positionSize.toFixed(4)}
                    </p>
                  </div>

                  {/* Total Position Value */}
                  <div className="bg-gray-900/80 p-2 sm:p-3 rounded-xl border border-gray-800/70 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-gray-400 text-[10px] sm:text-xs mb-1">
                      <span className="truncate">ارزش کل</span>
                      {renderInfoButton('value', 'center')}
                    </div>
                    <p dir="ltr" className="font-mono text-xs sm:text-sm text-gray-200 font-bold text-left truncate">
                      {calcResult.warning || !calcResult.positionValue ? '0.0' : `$${calcResult.positionValue.toFixed(1)}`}
                    </p>
                  </div>

                  {/* Risk / Reward */}
                  <div className="bg-gray-900/80 p-2 sm:p-3 rounded-xl border border-gray-800/70 flex flex-col justify-between">
                    <div className="flex items-center justify-between text-gray-400 text-[10px] sm:text-xs mb-1">
                      <span>R / R</span>
                      {renderInfoButton('rr', 'left')}
                    </div>
                    <div dir="ltr" className="font-mono text-xs sm:text-sm text-emerald-400 font-bold text-left truncate">
                      {calcResult.rrRatio ? `1:${calcResult.rrRatio}` : '—'}
                      {calcResult.potentialProfit > 0 && (
                        <span className="text-[9px] sm:text-[10px] text-emerald-500/80 block">
                          +${calcResult.potentialProfit.toFixed(1)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Save to Journal Button */}
              <button
                type="button"
                onClick={handleSaveTrade}
                disabled={!!calcResult.warning || !calcResult.positionSize}
                className={`w-full py-3.5 sm:py-4 rounded-xl font-bold text-xs sm:text-sm flex justify-center items-center gap-2 transition-all ${
                  calcResult.warning || !calcResult.positionSize
                    ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-900/30 active:scale-[0.98]'
                }`}
              >
                {saveSuccessToast ? (
                  <>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                    با موفقیت به همراه اسنپ‌شات چارت ثبت شد!
                  </>
                ) : (
                  <>
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                    ثبت معامله در ژورنال (+ اسنپ‌شات چارت)
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ==================== TAB 2: TRADE JOURNAL ==================== */}
        {activeTab === 'journal' && !draftTrade && (
          <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 pb-6" onClick={() => setOpenStatusMenuId(null)}>
            {/* Mini Portfolio Analytics Header */}
            <div className="grid grid-cols-3 gap-2 sm:gap-3 bg-gray-950 p-3 sm:p-4 rounded-xl border border-gray-800">
              <div className="text-center">
                <span className="text-[10px] sm:text-xs text-gray-400 block">وین‌ریت (Win Rate)</span>
                <span className="font-mono text-sm sm:text-lg font-bold text-emerald-400">{journalStats.winRate}%</span>
              </div>
              <div className="text-center border-x border-gray-800">
                <span className="text-[10px] sm:text-xs text-gray-400 block">معاملات بسته</span>
                <span className="font-mono text-sm sm:text-lg font-bold text-white">{journalStats.closedCount}</span>
              </div>
              <div className="text-center">
                <span className="text-[10px] sm:text-xs text-gray-400 block">کل معاملات</span>
                <span className="font-mono text-sm sm:text-lg font-bold text-blue-400">{journalStats.total}</span>
              </div>
            </div>

            <div className="flex justify-between items-center px-1">
              <h2 className="text-xs sm:text-sm font-bold text-gray-300">لیست معاملات شما</h2>
              <span className="text-[10px] sm:text-xs text-gray-500">برای مشاهده چارت و یادداشت کلیک کنید</span>
            </div>

            {/* Responsive List of Trade Cards */}
            <div className="space-y-2.5 sm:space-y-3">
              {trades.length === 0 ? (
                <div className="bg-gray-950/60 border border-dashed border-gray-800 rounded-2xl p-8 text-center space-y-3">
                  <div className="w-12 h-12 mx-auto rounded-2xl bg-gray-900 border border-gray-800 flex items-center justify-center text-gray-500 text-xl">
                    📖
                  </div>
                  <div>
                    <h3 className="text-xs sm:text-sm font-bold text-gray-300">هنوز معامله‌ای در ژورنال ثبت نشده است</h3>
                    <p className="text-[11px] sm:text-xs text-gray-500 mt-1 max-w-xs mx-auto">
                      از تب ماشین‌حساب استفاده کنید تا پس از محاسبه دقیق حجم و ریسک، پوزیشن خود را به صورت خودکار در ژورنال ثبت کنید.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveTab('calc')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 rounded-xl text-xs font-bold transition-all"
                  >
                    رفتن به ماشین‌حساب معاملاتی 🧮
                  </button>
                </div>
              ) : (
                trades.map((trade) => {
                const resultMeta = getTradeResultMeta(trade);

                return (
                  <div
                    key={trade.id}
                    onClick={() => {
                      setSelectedTradeId(trade.id);
                      setIsStrategyBarOpen(false);
                    }}
                    className="bg-gray-950 hover:bg-gray-900/90 border border-gray-800 rounded-xl p-3 sm:p-4 transition-all cursor-pointer relative"
                  >
                    <div className="flex justify-between items-center gap-2">
                      {/* Right: Pair & Direction */}
                      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                        <span className={`px-2 py-1 rounded-lg text-[10px] sm:text-xs font-mono font-bold shrink-0 ${
                          trade.isLong ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                        }`}>
                          {trade.isLong ? 'LONG' : 'SHORT'}
                        </span>
                        <div className="min-w-0">
                          <div className="text-xs sm:text-sm font-bold text-white flex flex-wrap items-center gap-1.5">
                            <span>{trade.pair}</span>
                            <span className="text-[10px] font-mono text-gray-400 bg-gray-800 px-1.5 rounded">{trade.leverage}x</span>
                            {(trade.hasChartSnapshot || trade.customChartUrl) && (
                              <span className="text-[9px] sm:text-[10px] bg-blue-500/15 text-blue-400 border border-blue-500/30 px-1.5 py-0.2 rounded flex items-center gap-1" title="دارای تصویر چارت">
                                📊 چارت
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] sm:text-xs text-gray-500 block mt-0.5 truncate">{trade.strategy} • {trade.date}</span>
                        </div>
                      </div>

                      {/* Left: Interactive Status Button, Delete Button & Popover Box */}
                      <div className="relative flex items-center gap-1.5 shrink-0" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => setOpenStatusMenuId(openStatusMenuId === trade.id ? null : trade.id)}
                          className={`px-2 sm:px-2.5 py-1 rounded-lg border text-[10px] sm:text-[11px] font-bold flex items-center gap-1 transition-all ${resultMeta.bg}`}
                        >
                          {resultMeta.badge}
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 12 15 18 9"/></svg>
                        </button>

                        <button
                          type="button"
                          onClick={(e) => handleDeleteTrade(trade.id, e)}
                          className="w-7 h-7 rounded-lg bg-gray-900 hover:bg-rose-500/20 text-gray-500 hover:text-rose-400 border border-gray-800 flex items-center justify-center transition-colors"
                          title="حذف معامله"
                        >
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                        </button>

                        {/* Animated Popover Button Box for TP / SL / Draw */}
                        {openStatusMenuId === trade.id && (
                          <div className="absolute left-0 top-9 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-1.5 flex items-center gap-1 z-30">
                            <button
                              type="button"
                              onClick={(e) => updateTradeStatus(trade.id, 'TP', e)}
                              className="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500 text-emerald-300 hover:text-white text-[10px] font-bold transition-colors"
                            >
                              TP
                            </button>
                            <button
                              type="button"
                              onClick={(e) => updateTradeStatus(trade.id, 'SL', e)}
                              className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500 text-rose-300 hover:text-white text-[10px] font-bold transition-colors"
                            >
                              SL
                            </button>
                            <button
                              type="button"
                              onClick={(e) => updateTradeStatus(trade.id, 'DRAW', e)}
                              className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500 text-amber-300 hover:text-white text-[10px] font-bold transition-colors"
                            >
                              Draw
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Summary Row: Entry, SL, TP, and Trade Result PnL */}
                    <div dir="ltr" className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-3 pt-2.5 border-t border-gray-800/70 text-[11px] sm:text-xs font-mono">
                      <div>
                        <span className="text-gray-500 text-[10px] block">Entry</span>
                        <span className="text-gray-200 font-semibold">${trade.entryPrice}</span>
                      </div>
                      <div className="text-right sm:text-center">
                        <span className="text-gray-500 text-[10px] block">Stop Loss</span>
                        <span className="text-rose-400 font-semibold">{trade.stopLoss !== '—' ? `$${trade.stopLoss}` : '—'}</span>
                      </div>
                      <div className="text-left sm:text-center">
                        <span className="text-gray-500 text-[10px] block">Take Profit</span>
                        <span className="text-emerald-400 font-semibold">{trade.takeProfit !== '—' ? `$${trade.takeProfit}` : '—'}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-gray-500 text-[10px] block">Result</span>
                        <span className={`font-bold ${resultMeta.color}`}>{resultMeta.pnlText}</span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
            </div>
          </div>
        )}

        {/* ==================== LAYER 2: TRADE DETAIL VIEW ==================== */}
        {activeTab === 'journal' && draftTrade && (
          <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 pb-6">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
              <button
                type="button"
                onClick={() => setSelectedTradeId(null)}
                className="flex items-center gap-1.5 text-xs sm:text-sm text-blue-400 hover:text-blue-300 font-bold"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="9 18 15 12 9 6"/></svg>
                بازگشت به لیست ژورنال
              </button>
              <div className="flex flex-wrap items-center gap-2">
                {hasUnsavedChanges && (
                  <span className="text-[10px] bg-amber-500/15 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full animate-pulse">
                    تغییرات ذخیره نشده
                  </span>
                )}
                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                  draftTrade.isLong ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                }`}>
                  {draftTrade.isLong ? 'LONG' : 'SHORT'}
                </span>
                <span className="text-[11px] sm:text-xs font-mono text-gray-300 font-bold">{draftTrade.pair}</span>
              </div>
            </div>

            {/* Trade Result & Status Bar */}
            {(() => {
              const meta = getTradeResultMeta(draftTrade);
              return (
                <div className="bg-gray-950 p-3.5 sm:p-4 rounded-xl border border-gray-800 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <span className="text-[10px] sm:text-xs text-gray-400 block">نتیجه معامله (Trade Result)</span>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`text-xs sm:text-sm font-bold ${meta.color}`}>{meta.badge}</span>
                        <span dir="ltr" className={`font-mono text-xs sm:text-sm font-bold px-2 py-0.5 rounded bg-gray-900 ${meta.color}`}>
                          {meta.pnlText}
                        </span>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-1 bg-gray-900 p-1 rounded-xl border border-gray-800">
                      {[
                        { id: 'TP', label: 'TP سود', active: 'bg-emerald-600 text-white' },
                        { id: 'SL', label: 'SL ضرر', active: 'bg-rose-600 text-white' },
                        { id: 'DRAW', label: 'Draw', active: 'bg-amber-600 text-white' },
                        { id: 'OPEN', label: 'باز', active: 'bg-blue-600 text-white' }
                      ].map((st) => (
                        <button
                          key={st.id}
                          type="button"
                          onClick={() => updateDraftField('status', st.id)}
                          className={`px-2 sm:px-2.5 py-1 rounded-lg text-[10px] sm:text-xs font-bold transition-all ${
                            draftTrade.status === st.id ? st.active : 'text-gray-400 hover:text-gray-200'
                          }`}
                        >
                          {st.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div dir="ltr" className="grid grid-cols-3 gap-2 pt-2.5 border-t border-gray-800/80 text-center font-mono text-xs sm:text-sm">
                    <div>
                      <span className="text-[10px] text-gray-500 block">Entry</span>
                      <span className="text-white font-bold">${draftTrade.entryPrice}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-gray-500 block">Stop Loss</span>
                      <span className="text-rose-400 font-bold">{draftTrade.stopLoss !== '—' ? `$${draftTrade.stopLoss}` : '—'}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-gray-500 block">Take Profit</span>
                      <span className="text-emerald-400 font-bold">{draftTrade.takeProfit !== '—' ? `$${draftTrade.takeProfit}` : '—'}</span>
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* ==================== CHART SNAPSHOT SECTION ==================== */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="text-xs sm:text-sm font-bold text-gray-300 flex items-center gap-1.5">
                  <svg width="14" height="14" className="text-blue-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
                  تصویر چارت در لحظه معامله
                </label>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleCustomChartUpload}
                  className="hidden"
                />

                <div className="flex items-center gap-1.5">
                  {(draftTrade.hasChartSnapshot || draftTrade.customChartUrl) && !draftTrade.customChartUrl && (
                    <div className="flex bg-gray-950 p-0.5 rounded-lg border border-gray-800 shrink-0">
                      {['15m', '1H', '4H'].map((tf) => (
                        <button
                          key={tf}
                          type="button"
                          onClick={() => updateDraftField('chartTimeframe', tf)}
                          className={`px-1.5 sm:px-2 py-0.5 rounded text-[9px] sm:text-[10px] font-mono font-bold transition-colors ${
                            (draftTrade.chartTimeframe || '1H') === tf
                              ? 'bg-blue-600 text-white'
                              : 'text-gray-500 hover:text-gray-300'
                          }`}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="bg-gray-900 hover:bg-gray-800 border border-gray-700 text-gray-300 px-2 sm:px-2.5 py-1 rounded-lg text-[10px] sm:text-xs font-medium transition-colors"
                  >
                    + آپلود تصویر
                  </button>
                </div>
              </div>

              {draftTrade.hasChartSnapshot || draftTrade.customChartUrl ? (
                <div className="relative group">
                  <div
                    onClick={() => setIsChartZoomOpen(true)}
                    className="cursor-zoom-in transition-transform active:scale-[0.99]"
                  >
                    {renderCandlestickSnapshot(draftTrade, false)}
                  </div>

                  {/* Action Overlay Buttons on Chart */}
                  <div className="flex items-center justify-between mt-1.5 px-1">
                    <button
                      type="button"
                      onClick={() => setIsChartZoomOpen(true)}
                      className="text-[10px] sm:text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1 font-medium"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
                      بزرگ‌نمایی تصویر چارت
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        updateDraftField('hasChartSnapshot', false);
                        updateDraftField('customChartUrl', null);
                      }}
                      className="text-[10px] sm:text-xs text-gray-500 hover:text-rose-400 transition-colors"
                    >
                      حذف تصویر چارت
                    </button>
                  </div>
                </div>
              ) : (
                <div className="bg-gray-950/70 border border-dashed border-gray-800 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[11px] sm:text-xs text-gray-500">تصویری برای این معامله پیوست نشده است.</span>
                  <button
                    type="button"
                    onClick={() => updateDraftField('hasChartSnapshot', true)}
                    className="bg-blue-600/15 hover:bg-blue-600/25 border border-blue-500/30 text-blue-400 px-2.5 py-1 rounded-lg text-[10px] sm:text-xs font-bold transition-colors"
                  >
                    تولید خودکار اسنپ‌شات چارت
                  </button>
                </div>
              )}
            </div>

            {/* Full-Screen Chart Zoom Lightbox Modal */}
            {isChartZoomOpen && (
              <div
                onClick={() => setIsChartZoomOpen(false)}
                className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex flex-col items-center justify-center p-3 sm:p-6"
              >
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="w-full max-w-lg md:max-w-2xl bg-gray-900 border border-gray-700 rounded-2xl p-3 sm:p-4 space-y-3 shadow-2xl"
                >
                  <div className="flex items-center justify-between border-b border-gray-800 pb-2">
                    <span className="text-xs sm:text-sm font-bold text-white flex items-center gap-2">
                      📊 اسنپ‌شات چارت {draftTrade.pair}
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsChartZoomOpen(false)}
                      className="w-6 h-6 sm:w-7 sm:h-7 rounded-lg bg-gray-800 text-gray-400 hover:text-white flex items-center justify-center text-xs"
                    >
                      ✕
                    </button>
                  </div>
                  {renderCandlestickSnapshot(draftTrade, true)}
                  <div dir="ltr" className="grid grid-cols-3 gap-2 text-center font-mono text-[11px] sm:text-xs bg-gray-950 p-2 sm:p-2.5 rounded-xl border border-gray-800">
                    <div>
                      <span className="text-gray-500 text-[9px] sm:text-[10px] block">ENTRY</span>
                      <span className="text-blue-400 font-bold">${draftTrade.entryPrice}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 text-[9px] sm:text-[10px] block">STOP LOSS</span>
                      <span className="text-rose-400 font-bold">{draftTrade.stopLoss !== '—' ? `$${draftTrade.stopLoss}` : '—'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500 text-[9px] sm:text-[10px] block">TAKE PROFIT</span>
                      <span className="text-emerald-400 font-bold">{draftTrade.takeProfit !== '—' ? `$${draftTrade.takeProfit}` : '—'}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Expandable Strategy Selector Bar (Personal with Delete + Searchable General) */}
            <div className="space-y-1.5 relative">
              <label className="text-xs sm:text-sm font-bold text-gray-300 block">استراتژی معاملاتی</label>

              {/* Closed/Open Bar Trigger */}
              <button
                type="button"
                onClick={() => setIsStrategyBarOpen(!isStrategyBarOpen)}
                className="w-full bg-gray-950 hover:bg-gray-900 border border-gray-800 rounded-xl px-3.5 py-2.5 sm:py-3 flex items-center justify-between gap-2 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0"></span>
                  <span className="text-xs sm:text-sm font-bold text-white truncate">{draftTrade.strategy}</span>
                  {customStrategies.includes(draftTrade.strategy) && (
                    <span className="text-[9px] sm:text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded shrink-0">شخصی</span>
                  )}
                </div>
                <div className="flex items-center gap-1 text-[10px] sm:text-xs text-gray-400 shrink-0">
                  <span className="sm:hidden">{isStrategyBarOpen ? 'بستن' : 'تغییر'}</span><span className="hidden sm:inline">{isStrategyBarOpen ? 'بستن لیست' : 'مدیریت یا جستجوی استراتژی'}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`transition-transform ${isStrategyBarOpen ? 'rotate-180' : ''}`}><polyline points="6 9 12 15 18 9"/></svg>
                </div>
              </button>

              {/* Expandable Strategy Box */}
              {isStrategyBarOpen && (
                <div className="bg-gray-950 border border-gray-700 rounded-xl p-3 sm:p-4 space-y-3 shadow-xl">
                  {/* Add Personal Strategy Input */}
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={newStrategyInput}
                      onChange={(e) => setNewStrategyInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddCustomStrategy()}
                      placeholder="افزودن استراتژی شخصی جدید..."
                      className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-2.5 py-1.5 sm:py-2 text-xs text-white outline-none focus:border-purple-500"
                    />
                    <button
                      type="button"
                      onClick={handleAddCustomStrategy}
                      className="bg-purple-600 hover:bg-purple-500 text-white px-3 py-1.5 sm:py-2 rounded-lg text-xs font-bold transition-colors shrink-0"
                    >
                      + افزودن
                    </button>
                  </div>

                  {/* Personal Strategies Section with Delete (✕) Button */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] sm:text-xs font-bold text-purple-400 block">استراتژی‌های شخصی من</span>
                    {customStrategies.length === 0 ? (
                      <p className="text-[10px] text-gray-500 py-1">هنوز استراتژی شخصی اضافه نکرده‌اید.</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
                        {customStrategies.map((strat) => {
                          const isSelected = draftTrade.strategy === strat;
                          return (
                            <div
                              key={strat}
                              onClick={() => {
                                updateDraftField('strategy', strat);
                                setIsStrategyBarOpen(false);
                              }}
                              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] sm:text-xs cursor-pointer transition-all ${
                                isSelected
                                  ? 'bg-purple-600 text-white font-bold shadow'
                                  : 'bg-gray-900 text-gray-300 border border-gray-800 hover:border-purple-500/50'
                              }`}
                            >
                              <span>★ {strat}</span>
                              <button
                                type="button"
                                onClick={(e) => handleDeleteCustomStrategy(strat, e)}
                                className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] transition-colors ${
                                  isSelected
                                    ? 'hover:bg-purple-700 text-purple-200 hover:text-white'
                                    : 'hover:bg-rose-500/20 text-gray-500 hover:text-rose-400'
                                }`}
                                title="حذف استراتژی شخصی"
                              >
                                ✕
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Searchable General Strategies Bar */}
                  <div className="space-y-2 pt-2 border-t border-gray-800">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] sm:text-xs font-bold text-gray-400">جستجو در استراتژی‌های عمومی</span>
                      <span className="text-[9px] sm:text-[10px] text-gray-500">{filteredGeneralStrategies.length} مورد</span>
                    </div>
                    <div className="relative">
                      <input
                        type="text"
                        value={strategySearch}
                        onChange={(e) => setStrategySearch(e.target.value)}
                        placeholder="جستجوی استراتژی (مثلاً ICT، RSI، Breakout)..."
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg pr-8 pl-3 py-1.5 sm:py-2 text-xs text-white outline-none focus:border-blue-500"
                      />
                      <svg width="13" height="13" className="text-gray-500 absolute right-2.5 top-1/2 -translate-y-1/2" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                    </div>
                    <div className="max-h-32 overflow-y-auto space-y-1 pr-0.5">
                      {filteredGeneralStrategies.map((strat) => (
                        <button
                          key={strat}
                          type="button"
                          onClick={() => {
                            updateDraftField('strategy', strat);
                            setIsStrategyBarOpen(false);
                            setStrategySearch('');
                          }}
                          className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-mono transition-colors ${
                            draftTrade.strategy === strat
                              ? 'bg-blue-600/20 text-blue-400 font-bold border border-blue-500/30'
                              : 'hover:bg-gray-900 text-gray-300'
                          }`}
                        >
                          <span>{strat}</span>
                          {draftTrade.strategy === strat && <span className="text-[10px]">✓</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Entry Reasons & Notes (Side-by-side on medium/desktop screens, stacked on mobile) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
              {/* Entry Reasons */}
              <div className="space-y-1.5">
                <label className="text-xs sm:text-sm font-bold text-gray-300 block">دلایل ورود به معامله</label>
                <textarea
                  rows="3"
                  value={draftTrade.entryReason}
                  onChange={(e) => updateDraftField('entryReason', e.target.value)}
                  placeholder="چرا وارد این پوزیشن شدید؟ (مثلاً شکست مقاومت، واگرایی RSI و...)"
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs sm:text-sm text-white outline-none focus:border-blue-500 leading-relaxed"
                />
              </div>

              {/* Lessons Learned / Notes */}
              <div className="space-y-1.5">
                <label className="text-xs sm:text-sm font-bold text-gray-300 block">نکات و درس‌های آموخته شده (Notes)</label>
                <textarea
                  rows="3"
                  value={draftTrade.notes}
                  onChange={(e) => updateDraftField('notes', e.target.value)}
                  placeholder="نتیجه روانی و تکنیکال این ترید چه بود؟ چه نکته‌ای یاد گرفتید؟"
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs sm:text-sm text-white outline-none focus:border-blue-500 leading-relaxed"
                />
              </div>
            </div>

            {/* Action Buttons: Save & Delete Trade */}
            <div className="pt-2 flex items-center gap-2">
              {(hasUnsavedChanges || detailSaveToast) ? (
                <button
                  type="button"
                  onClick={handleSaveDraftChanges}
                  className={`flex-1 py-3 sm:py-3.5 rounded-xl font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-lg transition-all ${
                    detailSaveToast
                      ? 'bg-emerald-600 text-white shadow-emerald-900/30'
                      : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-900/40'
                  }`}
                >
                  {detailSaveToast ? (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                      تغییرات با موفقیت ذخیره شد!
                    </>
                  ) : (
                    <>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                      ذخیره تغییرات معامله
                    </>
                  )}
                </button>
              ) : (
                <div className="flex-1"></div>
              )}

              <button
                type="button"
                onClick={() => handleDeleteTrade(draftTrade.id)}
                className="px-4 py-3 sm:py-3.5 rounded-xl font-bold text-xs sm:text-sm bg-rose-600/15 hover:bg-rose-600/25 border border-rose-500/30 text-rose-400 hover:text-rose-300 flex items-center justify-center gap-1.5 transition-all shrink-0 active:scale-95"
                title="حذف معامله از ژورنال"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
                <span>حذف معامله</span>
              </button>
            </div>
          </div>
        )}

        {/* ==================== TAB 3: PORTFOLIO ANALYTICS (پورتفولیو) ==================== */}
        {activeTab === 'portfolio' && (
          <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 pb-6">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
              <div>
                <h2 className="text-sm sm:text-base font-extrabold text-white">پورتفولیو و تحلیل عملکرد</h2>
                <span className="text-[10px] sm:text-xs text-gray-400">بررسی آماری معاملات و استراتژی‌های شما</span>
              </div>
              <span className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2.5 py-1 rounded-xl text-xs sm:text-sm font-mono font-bold">
                Win Rate: {journalStats.winRate}%
              </span>
            </div>

            {/* Equity & PnL Summary */}
            <div className="grid grid-cols-1 min-[360px]:grid-cols-2 gap-3">
              <div className="bg-gray-950 p-3.5 sm:p-4 rounded-2xl border border-gray-800">
                <span className="text-[10px] sm:text-xs text-gray-400 block">مجموع سودهای کسب‌شده</span>
                <span dir="ltr" className="font-mono text-base sm:text-xl font-extrabold text-emerald-400 mt-1 block">
                  +${journalStats.totalProfit.toFixed(2)}
                </span>
                <span className="text-[9px] sm:text-[10px] text-gray-500 mt-1 block">{journalStats.wins} معامله برنده (TP)</span>
              </div>
              <div className="bg-gray-950 p-3.5 sm:p-4 rounded-2xl border border-gray-800">
                <span className="text-[10px] sm:text-xs text-gray-400 block">مجموع ضررهای ثبت‌شده</span>
                <span dir="ltr" className="font-mono text-base sm:text-xl font-extrabold text-rose-400 mt-1 block">
                  -${journalStats.totalLoss.toFixed(2)}
                </span>
                <span className="text-[9px] sm:text-[10px] text-gray-500 mt-1 block">{journalStats.losses} معامله بازنده (SL)</span>
              </div>
            </div>

            {/* Win / Loss Visual Progress Bar */}
            <div className="bg-gray-950 p-3.5 sm:p-4 rounded-2xl border border-gray-800 space-y-2">
              <div className="flex justify-between text-[11px] sm:text-xs">
                <span className="text-emerald-400 font-bold">برنده: {journalStats.wins}</span>
                <span className="text-gray-400">نسبت برد به باخت</span>
                <span className="text-rose-400 font-bold">بازنده: {journalStats.losses}</span>
              </div>
              <div className="w-full h-2.5 sm:h-3 bg-gray-800 rounded-full overflow-hidden flex">
                <div
                  style={{ width: `${journalStats.winRate}%` }}
                  className="bg-emerald-500 h-full transition-all duration-500"
                ></div>
                <div
                  style={{ width: `${100 - journalStats.winRate}%` }}
                  className="bg-rose-500 h-full transition-all duration-500"
                ></div>
              </div>
            </div>

            {/* Strategy Performance Breakdown */}
            <div className="space-y-2.5">
              <h3 className="text-xs sm:text-sm font-bold text-gray-300 px-1">عملکرد به تفکیک استراتژی</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 sm:gap-3">
                {journalStats.strategiesList.length === 0 ? (
                  <div className="col-span-full bg-gray-950/60 border border-dashed border-gray-800 rounded-xl p-4 text-center text-gray-500 text-xs">
                    هنوز داده‌ای برای تحلیل عملکرد استراتژی‌ها وجود ندارد.
                  </div>
                ) : (
                  journalStats.strategiesList.map((st) => {
                  const stWinRate = st.total > 0 ? Math.round((st.wins / st.total) * 100) : 0;
                  return (
                    <div key={st.name} className="bg-gray-950 p-3 sm:p-3.5 rounded-xl border border-gray-800 flex items-center justify-between">
                      <div>
                        <span className="text-xs sm:text-sm font-bold text-white block">{st.name}</span>
                        <span className="text-[10px] sm:text-xs text-gray-500">{st.total} معامله ثبت‌شده • وین‌ریت {stWinRate}%</span>
                      </div>
                      <span
                        dir="ltr"
                        className={`font-mono text-xs sm:text-sm font-bold px-2.5 py-1 rounded-lg ${
                          st.pnl >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
                        }`}
                      >
                        {st.pnl >= 0 ? `+$${st.pnl.toFixed(2)}` : `-$${Math.abs(st.pnl).toFixed(2)}`}
                      </span>
                    </div>
                  );
                })
              )}
              </div>
            </div>
          </div>
        )}

        {/* ==================== TAB 4: EMPTY PLACEHOLDER SLOT ==================== */}
        {activeTab === 'empty' && (
          <div className="p-6 flex-1 min-h-0 overflow-y-auto flex flex-col items-center justify-center text-center space-y-3 pb-6">
            <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-gray-950 border border-dashed border-gray-700 flex items-center justify-center text-gray-500">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            </div>
            <h3 className="text-sm sm:text-base font-bold text-gray-300">بخش قابلیت‌های آینده</h3>
            <p className="text-xs sm:text-sm text-gray-500 max-w-xs sm:max-w-sm leading-relaxed">
              این جایگاه برای فیچرهای بعدی شما (مانند هشدار هوشمند قیمت، غربالگر بازار یا دستیار هوش مصنوعی) رزرو شده است.
            </p>
          </div>
        )}

        {/* ==================== BOTTOM NAVIGATION BAR (DOCK) ==================== */}
        <div className="shrink-0 bg-gray-950/95 backdrop-blur-md border-t border-gray-800/90 px-2 sm:px-4 py-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] z-30">
          <div className="max-w-md mx-auto grid grid-cols-5 items-end">
            
            {/* 1. Far Right: Journal (ژورنال) */}
            <button
              type="button"
              onClick={() => { setActiveTab('journal'); setSelectedTradeId(null); }}
              className={`flex flex-col items-center justify-center py-1 rounded-xl transition-all relative ${
                activeTab === 'journal' ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <div className="relative">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>
                <span className="-top-1.5 -right-2.5 bg-gray-800 border border-gray-700 text-gray-300 text-[8px] font-mono px-1 rounded-full absolute">
                  {trades.length}
                </span>
              </div>
              <span className="text-[9px] sm:text-[10px] font-bold mt-1">ژورنال</span>
            </button>

            {/* 2. Right of Home: Risk Calculator (ماشین‌حساب) */}
            <button
              type="button"
              onClick={() => { setActiveTab('calc'); setSelectedTradeId(null); }}
              className={`flex flex-col items-center justify-center py-1 rounded-xl transition-all ${
                activeTab === 'calc' ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="16" y1="14" x2="16" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/></svg>
              <span className="text-[9px] sm:text-[10px] font-bold mt-1">ماشین‌حساب</span>
            </button>

            {/* 3. Center (Larger & Prominent): Home (صفحه اصلی) */}
            <div className="flex flex-col items-center justify-end py-1">
              <button
                type="button"
                onClick={() => { setActiveTab('home'); setSelectedTradeId(null); }}
                className={`-mt-4 w-11 h-11 sm:w-12 sm:h-12 rounded-2xl flex items-center justify-center transition-all border-4 border-gray-900 shadow-xl ${
                  activeTab === 'home'
                    ? 'bg-gradient-to-tr from-blue-600 to-indigo-500 text-white shadow-blue-500/40 scale-105'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
                }`}
              >
                <svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
              </button>
              <span className={`text-[10px] sm:text-[11px] font-extrabold mt-1 ${activeTab === 'home' ? 'text-blue-400' : 'text-gray-400'}`}>
                صفحه اصلی
              </span>
            </div>

            {/* 4. Left of Home: Empty Button (فعلاً خالی) */}
            <button
              type="button"
              onClick={() => { setActiveTab('empty'); setSelectedTradeId(null); }}
              className={`flex flex-col items-center justify-center py-1 rounded-xl transition-all ${
                activeTab === 'empty' ? 'text-blue-400' : 'text-gray-600 hover:text-gray-400'
              }`}
            >
              <div className="w-[18px] h-[18px] rounded-md border border-dashed border-current flex items-center justify-center">
                <span className="w-1 h-1 rounded-full bg-current"></span>
              </div>
              <span className="text-[9px] sm:text-[10px] font-medium mt-1">به‌زودی</span>
            </button>

            {/* 5. Far Left: Portfolio (پورتفولیو) */}
            <button
              type="button"
              onClick={() => { setActiveTab('portfolio'); setSelectedTradeId(null); }}
              className={`flex flex-col items-center justify-center py-1 rounded-xl transition-all ${
                activeTab === 'portfolio' ? 'text-blue-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/></svg>
              <span className="text-[9px] sm:text-[10px] font-bold mt-1">پورتفولیو</span>
            </button>

          </div>
        </div>

      </div>
    </div>
  );
};

export default App;