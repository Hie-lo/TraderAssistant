import React, { useState } from 'react';

export const VIP_WELCOME_DISMISSED_KEY = 'vip_welcome_dismissed_v1';

const VipWelcomeModal = ({ isOpen, onClose, userName }) => {
  const [dontShowAgain, setDontShowAgain] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (dontShowAgain) {
      try {
        window.localStorage.setItem(VIP_WELCOME_DISMISSED_KEY, '1');
      } catch (e) {
        // Ignore restricted WebView localStorage failures
      }
    }
    onClose();
  };

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
      onClick={handleConfirm}
    >
      <div
        className="w-full max-w-sm rounded-3xl border border-amber-500/50 bg-gradient-to-b from-amber-950/60 via-gray-900 to-gray-950 p-5 shadow-2xl shadow-amber-500/20 text-right space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-amber-500 to-yellow-300 text-gray-950 flex items-center justify-center text-xl shadow-lg shadow-amber-500/30">
              👑
            </div>
            <div>
              <span className="inline-block text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 mb-1">
                عضویت ویژه فعال
              </span>
              <h2 className="text-base font-extrabold text-amber-200">
                خوش آمدید، {userName || 'معامله‌گر VIP'}!
              </h2>
            </div>
          </div>
          <button
            type="button"
            onClick={handleConfirm}
            className="text-amber-300/70 hover:text-amber-200 text-sm px-1.5 py-0.5 rounded-lg"
            aria-label="بستن"
          >
            ✕
          </button>
        </div>

        <p className="text-xs text-gray-300 leading-relaxed">
          حساب VIP شما فعال است. اکنون به <span className="text-amber-300 font-bold">سوپرچارت تعاملی</span> با داده‌های زنده صرافی، ابزارهای ترسیم خط روند، اندیکاتورهای تکنیکال و حالت تمام‌صفحه افقی دسترسی دارید.
        </p>

        <div className="bg-amber-500/10 border border-amber-500/25 rounded-2xl p-3 space-y-1.5 text-[11px] text-amber-100/90">
          <div>• ذخیره خودکار خطوط روند و تحلیل‌ها روی دستگاه شما</div>
          <div>• زوم دو انگشتی لمسی بدون تداخل با اسکرول تلگرام</div>
          <div>• تغییر چرخش خودکار به حالت افقی با دکمه Landscape</div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-gray-300 pt-1">
          <input
            type="checkbox"
            checked={dontShowAgain}
            onChange={(e) => setDontShowAgain(e.target.checked)}
            className="w-4 h-4 rounded border-amber-500/50 bg-gray-900 accent-amber-400"
          />
          <span>دیگر این پیام را نمایش نده (Don&apos;t show this again)</span>
        </label>

        <button
          type="button"
          onClick={handleConfirm}
          className="w-full py-2.5 rounded-xl bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 hover:brightness-110 text-gray-950 font-extrabold text-xs shadow-lg shadow-amber-500/25 transition-all"
        >
          شروع معامله با سوپرچارت
        </button>
      </div>
    </div>
  );
};

export default VipWelcomeModal;
