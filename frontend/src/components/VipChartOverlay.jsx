import React from 'react';

const VipChartOverlay = ({ onOpenVipModal }) => {
  return (
    <div dir="rtl" className="relative flex-1 min-h-[380px] flex flex-col items-center justify-center overflow-hidden rounded-2xl border border-amber-500/30 bg-gray-950 m-3">
      {/* Blurred static candlestick SVG backdrop (zero API requests fired) */}
      <svg
        viewBox="0 0 400 240"
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full opacity-35 blur-[6px] scale-105 pointer-events-none select-none"
        aria-hidden="true"
      >
        <rect width="400" height="240" fill="#020617" />
        <g stroke="#1e293b" strokeWidth="1" strokeDasharray="4 4">
          <line x1="0" y1="60" x2="400" y2="60" />
          <line x1="0" y1="120" x2="400" y2="120" />
          <line x1="0" y1="180" x2="400" y2="180" />
        </g>
        {[
          { x: 25, h: 45, l: 135, o: 110, c: 70, up: true },
          { x: 55, h: 60, l: 145, o: 75, c: 120, up: false },
          { x: 85, h: 55, l: 130, o: 118, c: 72, up: true },
          { x: 115, h: 40, l: 105, o: 72, c: 52, up: true },
          { x: 145, h: 48, l: 125, o: 56, c: 102, up: false },
          { x: 175, h: 80, l: 165, o: 102, c: 148, up: false },
          { x: 205, h: 95, l: 175, o: 145, c: 110, up: true },
          { x: 235, h: 65, l: 140, o: 110, c: 78, up: true },
          { x: 265, h: 35, l: 105, o: 80, c: 48, up: true },
          { x: 295, h: 42, l: 118, o: 52, c: 92, up: false },
          { x: 325, h: 50, l: 120, o: 90, c: 58, up: true },
          { x: 355, h: 25, l: 90, o: 58, c: 34, up: true },
        ].map((c, idx) => (
          <g key={idx}>
            <line x1={c.x} y1={c.h} x2={c.x} y2={c.l} stroke={c.up ? '#10b981' : '#f43f5e'} strokeWidth="2" />
            <rect
              x={c.x - 7}
              y={Math.min(c.o, c.c)}
              width="14"
              height={Math.max(8, Math.abs(c.c - c.o))}
              rx="2"
              fill={c.up ? '#10b981' : '#f43f5e'}
            />
          </g>
        ))}
        <line x1="20" y1="155" x2="375" y2="42" stroke="#f59e0b" strokeWidth="2.5" />
      </svg>

      {/* Padlock & VIP Upgrade Card */}
      <div className="relative z-10 max-w-xs mx-auto p-6 rounded-3xl bg-gray-950/90 border border-amber-500/40 shadow-2xl shadow-amber-500/15 text-center space-y-4 backdrop-blur-md">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-gradient-to-tr from-amber-500/20 to-yellow-500/10 border border-amber-500/40 flex items-center justify-center text-amber-400 shadow-inner">
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
        </div>

        <div className="space-y-1.5">
          <h3 className="text-sm font-extrabold text-amber-300">
            سوپرچارت اختصاصی کاربران VIP
          </h3>
          <p className="text-[11px] text-gray-300 leading-relaxed">
            برای استفاده از سوپرچارت زنده، ابزارهای ترسیم و اندیکاتورهای پیشرفته، اشتراک VIP تهیه کنید.
          </p>
          <p className="text-[10px] text-gray-500 font-mono">
            Purchase VIP to use Superchart
          </p>
        </div>

        <button
          type="button"
          onClick={onOpenVipModal}
          className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 hover:brightness-110 text-gray-950 font-extrabold text-xs shadow-lg shadow-amber-500/25 transition-all"
        >
          👑 خرید اشتراک VIP
        </button>
      </div>
    </div>
  );
};

export default VipChartOverlay;
