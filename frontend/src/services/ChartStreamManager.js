import { api } from '../api/client.js';

/**
 * Leading + trailing throttle (200ms default) so bursts never lock the canvas thread
 * while ensuring the latest price tick always renders cleanly.
 */
function createThrottle(fn, waitMs = 200) {
  let lastCallTime = 0;
  let timerId = null;
  let pendingArgs = null;

  const throttled = (...args) => {
    const now = Date.now();
    const remaining = waitMs - (now - lastCallTime);
    pendingArgs = args;

    if (remaining <= 0 || remaining > waitMs) {
      if (timerId !== null) {
        clearTimeout(timerId);
        timerId = null;
      }
      lastCallTime = now;
      const invokeArgs = pendingArgs;
      pendingArgs = null;
      fn(...invokeArgs);
    } else if (timerId === null) {
      timerId = setTimeout(() => {
        lastCallTime = Date.now();
        timerId = null;
        if (pendingArgs) {
          const invokeArgs = pendingArgs;
          pendingArgs = null;
          fn(...invokeArgs);
        }
      }, remaining);
    }
  };

  throttled.cancel = () => {
    if (timerId !== null) {
      clearTimeout(timerId);
      timerId = null;
    }
    pendingArgs = null;
  };

  return throttled;
}

export function normalizeCandlePayload(raw) {
  if (!raw || typeof raw !== 'object') return null;
  const tsNum = Number(raw.timestamp);
  const timestamp = tsNum > 0 && tsNum < 1e12 ? Math.trunc(tsNum * 1000) : Math.trunc(tsNum);
  const open = Number(raw.open);
  const high = Number(raw.high);
  const low = Number(raw.low);
  const close = Number(raw.close);
  const volume = Number(raw.volume ?? 0);

  if (![timestamp, open, high, low, close].every(Number.isFinite) || timestamp <= 0) {
    return null;
  }
  return {
    timestamp,
    open,
    high,
    low,
    close,
    volume: Number.isFinite(volume) ? volume : 0,
  };
}

/**
 * Vanilla JS Pub/Sub Singleton driving klinecharts live updates completely outside React's render cycle.
 */
class ChartStreamManager {
  constructor(throttleMs = 200) {
    this._chart = null;
    this._symbol = null;
    this._timeframe = null;
    this._ws = null;
    this._reconnectTimer = null;
    this._pollTimer = null;
    this._pollController = null;
    this._hasInitialData = false;
    this._sessionToken = 0;

    this._throttledPush = createThrottle((candle) => {
      if (!this._chart || !this._hasInitialData) return;
      console.log('LIVE DATA RECEIVED:', candle);
      this._chart.updateData(candle);
    }, throttleMs);
  }

  attachChart(chartInstance) {
    if (!chartInstance) return;
    if (typeof chartInstance.updateData !== 'function') {
      chartInstance.updateData = (candle) => {
        chartInstance.getChartStore()?._addData(candle, 'update');
      };
    }
    this._chart = chartInstance;
  }

  setHasInitialData(ready) {
    this._hasInitialData = Boolean(ready);
  }

  connect(symbol, timeframe) {
    if (!symbol || !timeframe) return;
    if (
      this._symbol === symbol &&
      this._timeframe === timeframe &&
      this._ws &&
      (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    this.disconnect();
    this._symbol = symbol;
    this._timeframe = timeframe;
    const token = ++this._sessionToken;

    const openSocket = () => {
      if (token !== this._sessionToken || !this._chart) return;
      try {
        const ws = new WebSocket(api.getMarketStreamUrl(symbol, timeframe));
        this._ws = ws;

        ws.onmessage = (evt) => {
          if (token !== this._sessionToken) return;
          try {
            const parsed = JSON.parse(evt.data);
            const candle = normalizeCandlePayload(parsed?.bar || parsed);
            if (candle) {
              this._throttledPush(candle);
            }
          } catch (e) {
            // Ignore malformed WS payloads
          }
        };

        ws.onerror = () => {
          if (ws && ws.readyState !== WebSocket.CLOSED) {
            ws.close();
          }
        };

        ws.onclose = () => {
          if (token !== this._sessionToken) return;
          this._ws = null;
          this._reconnectTimer = setTimeout(openSocket, 3000);
        };
      } catch (e) {
        this._reconnectTimer = setTimeout(openSocket, 3000);
      }
    };

    openSocket();

    // Defensive REST polling backup strictly while WebSocket is disconnected/reconnecting
    this._pollController = new AbortController();
    this._pollTimer = setInterval(async () => {
      if (token !== this._sessionToken || !this._hasInitialData || !this._chart) return;
      if (this._ws && this._ws.readyState === WebSocket.OPEN) return;

      try {
        const res = await api.getMarketKlines(
          symbol,
          timeframe,
          2,
          null,
          this._pollController.signal
        );
        if (token !== this._sessionToken) return;
        const bars = Array.isArray(res?.bars) ? res.bars : [];
        if (bars.length > 0) {
          const candle = normalizeCandlePayload(bars[bars.length - 1]);
          if (candle) {
            this._throttledPush(candle);
          }
        }
      } catch (e) {
        // Ignore transient poll failures; WS auto-reconnect continues
      }
    }, 3000);
  }

  disconnect() {
    this._sessionToken += 1;
    this._throttledPush.cancel();

    if (this._reconnectTimer !== null) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
    if (this._pollTimer !== null) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    if (this._pollController) {
      this._pollController.abort();
      this._pollController = null;
    }
    if (this._ws) {
      this._ws.onclose = null;
      this._ws.onerror = null;
      this._ws.onmessage = null;
      this._ws.close();
      this._ws = null;
    }

    this._symbol = null;
    this._timeframe = null;
  }

  detachChart() {
    this.disconnect();
    this._hasInitialData = false;
    this._chart = null;
  }
}

export const chartStreamManager = new ChartStreamManager(200);
export default ChartStreamManager;
