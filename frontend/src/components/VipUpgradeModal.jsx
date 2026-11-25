import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';

const formatToman = (num) => {
  const n = Number(num);
  if (isNaN(n)) return String(num || '—');
  return n.toLocaleString('fa-IR') + ' تومان';
};

const formatDateShort = (isoStr) => {
  if (!isoStr) return 'نامحدود / بدون انقضا';
  try {
    return new Date(isoStr).toLocaleDateString('fa-IR');
  } catch {
    return isoStr.slice(0, 10);
  }
};

export default function VipUpgradeModal({
  isOpen,
  onClose,
  userRole,
  subscriptionEndDate,
  initialVipConfig,
  onVipUpdated,
}) {
  const [vipInfo, setVipInfo] = useState(initialVipConfig || {
    adminCardNumber: '6037-9911-0000-0000',
    adminCardName: 'مدیر سیستم',
    vipPrices: { '1': 290000, '3': 750000, '6': 1350000 },
  });
  const [payments, setPayments] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(1);
  const [receiptFile, setReceiptFile] = useState(null);
  const [receiptPreview, setReceiptPreview] = useState(null);
  const [copiedCard, setCopiedCard] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const fileRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    setFeedback(null);
    api.getVipPlans()
      .then((res) => {
        setVipInfo({
          adminCardNumber: res.adminCardNumber,
          adminCardName: res.adminCardName,
          vipPrices: res.vipPrices || { '1': 290000, '3': 750000, '6': 1350000 },
        });
        if (Array.isArray(res.payments)) setPayments(res.payments);
        if (onVipUpdated && res.role) {
          onVipUpdated(res.role, res.subscriptionEndDate);
        }
      })
      .catch((err) => {
        console.warn('Failed to fetch VIP plans:', err);
      });
  }, [isOpen]);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setReceiptFile(file);
    setFeedback(null);
    const reader = new FileReader();
    reader.onload = (ev) => setReceiptPreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const handleCopyCard = () => {
    navigator.clipboard?.writeText(vipInfo.adminCardNumber).catch(() => {});
    setCopiedCard(true);
    setTimeout(() => setCopiedCard(false), 1800);
  };

  const handleSubmitPayment = async () => {
    if (!receiptFile) {
      setFeedback({ type: 'error', msg: 'لطفاً ابتدا تصویر فیش واریزی را انتخاب کنید.' });
      return;
    }
    setIsSubmitting(true);
    setFeedback(null);
    try {
      const res = await api.submitVipPayment(selectedPlan, receiptFile);
      if (res.payment) {
        setPayments((prev) => [res.payment, ...prev]);
      }
      setReceiptFile(null);
      setReceiptPreview(null);
      setFeedback({ type: 'success', msg: res.message || 'فیش با موفقیت ثبت شد و در انتظار تأیید است.' });
    } catch (err) {
      setFeedback({ type: 'error', msg: err.message || 'خطا در ارسال فیش واریزی' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const plans = [
    { months: 1, title: '۱ ماهه', badge: 'اقتصادی' },
    { months: 3, title: '۳ ماهه', badge: 'محبوب 🔥' },
    { months: 6, title: '۶ ماهه', badge: 'به‌صرفه‌ترین 💎' },
  ];

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-5"
    >
      <div
        dir="rtl"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg max-h-[90dvh] overflow-y-auto bg-gray-900 border border-amber-500/30 rounded-2xl p-4 sm:p-5 space-y-4 shadow-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-lg">
              👑
            </span>
            <div>
              <h2 className="text-sm sm:text-base font-extrabold text-white">اشتراک ویژه (VIP)</h2>
              <span className="text-[10px] sm:text-xs text-gray-400 block">
                ژورنال نامحدود • هشدار قیمت نامحدود • تایم‌فریم‌های چارت
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-gray-800 text-gray-400 hover:text-white flex items-center justify-center text-xs"
          >
            ✕
          </button>
        </div>

        {/* Current Membership Banner */}
        <div className={`p-3 rounded-xl border flex items-center justify-between gap-2 ${
          userRole === 'VIP' || userRole === 'ADMIN'
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
            : 'bg-gray-950 border-gray-800 text-gray-300'
        }`}>
          <div className="text-xs">
            <span className="text-gray-400">وضعیت فعلی: </span>
            <span className="font-bold">
              {userRole === 'ADMIN' ? 'مدیر ارشد (دسترسی کامل)' : userRole === 'VIP' ? 'عضو ویژه VIP' : 'کاربر رایگان'}
            </span>
          </div>
          {userRole === 'VIP' && (
            <span className="text-[10px] font-mono bg-gray-900 px-2 py-1 rounded-lg border border-amber-500/20">
              اعتبار تا: {formatDateShort(subscriptionEndDate)}
            </span>
          )}
        </div>

        {/* Plan Selector */}
        <div className="space-y-2">
          <span className="text-xs font-bold text-gray-300 block">۱. انتخاب پلن اشتراک:</span>
          <div className="grid grid-cols-3 gap-2">
            {plans.map((pl) => {
              const priceVal = vipInfo.vipPrices?.[String(pl.months)] ?? vipInfo.vipPrices?.[pl.months] ?? 0;
              const active = selectedPlan === pl.months;
              return (
                <button
                  key={pl.months}
                  type="button"
                  onClick={() => setSelectedPlan(pl.months)}
                  className={`p-2.5 rounded-xl border text-center transition-all flex flex-col items-center gap-1 ${
                    active
                      ? 'bg-amber-500/15 border-amber-400 text-white shadow-lg shadow-amber-500/10'
                      : 'bg-gray-950 border-gray-800 text-gray-400 hover:border-gray-700'
                  }`}
                >
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-gray-900 text-amber-300 font-medium">
                    {pl.badge}
                  </span>
                  <span className="text-xs sm:text-sm font-extrabold text-white">{pl.title}</span>
                  <span className="text-[10px] sm:text-xs font-bold text-emerald-400">
                    {formatToman(priceVal)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Bank Card Details */}
        <div className="bg-gradient-to-l from-amber-950/30 via-gray-950 to-gray-950 border border-amber-500/25 rounded-xl p-3.5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-amber-300">۲. واریز وجه به شماره کارت:</span>
            <button
              type="button"
              onClick={handleCopyCard}
              className="px-2.5 py-1 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 text-[10px] font-bold transition-colors"
            >
              {copiedCard ? '✓ کپی شد' : 'کپی شماره کارت'}
            </button>
          </div>
          <div dir="ltr" className="font-mono text-sm sm:text-base font-extrabold text-white tracking-wider text-center bg-gray-900/90 py-2 rounded-lg border border-gray-800">
            {vipInfo.adminCardNumber}
          </div>
          <div className="text-[11px] text-gray-400 text-center">
            به نام: <span className="text-white font-bold">{vipInfo.adminCardName}</span>
          </div>
        </div>

        {/* Receipt Upload */}
        <div className="bg-gray-950 border border-gray-800 rounded-xl p-3.5 space-y-2.5">
          <span className="text-xs font-bold text-gray-300 block">۳. آپلود تصویر فیش واریزی:</span>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="w-full py-2.5 rounded-xl border border-dashed border-gray-700 hover:border-amber-500/50 bg-gray-900/60 text-xs text-gray-300 flex items-center justify-center gap-2 transition-colors"
          >
            <span>📎</span>
            <span>{receiptFile ? receiptFile.name : 'انتخاب تصویر فیش از گالری / فایل'}</span>
          </button>

          {receiptPreview && (
            <img
              src={receiptPreview}
              alt="پیش‌نمایش فیش"
              className="w-full max-h-40 object-contain rounded-lg border border-gray-800 bg-black/40"
            />
          )}

          {feedback && (
            <div className={`text-xs px-3 py-2 rounded-xl border ${
              feedback.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}>
              {feedback.msg}
            </div>
          )}

          <button
            type="button"
            onClick={handleSubmitPayment}
            disabled={isSubmitting || !receiptFile}
            className={`w-full py-2.5 rounded-xl text-xs sm:text-sm font-bold transition-all ${
              isSubmitting || !receiptFile
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                : 'bg-amber-500 hover:bg-amber-400 text-gray-950 shadow-lg shadow-amber-500/20'
            }`}
          >
            {isSubmitting ? 'در حال ارسال فیش...' : `ارسال فیش پلن ${selectedPlan} ماهه`}
          </button>
        </div>

        {/* User Payment History */}
        {payments.length > 0 && (
          <div className="space-y-1.5">
            <span className="text-[11px] font-bold text-gray-400 block">سوابق فیش‌های ارسالی شما:</span>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {payments.map((p) => (
                <div key={p.id} className="bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 flex items-center justify-between text-[11px]">
                  <span className="text-gray-300">پلن {p.planDuration} ماهه • <span className="font-mono text-gray-500">{p.createdAt}</span></span>
                  <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                    p.status === 'APPROVED'
                      ? 'bg-emerald-500/15 text-emerald-400'
                      : p.status === 'REJECTED'
                      ? 'bg-rose-500/15 text-rose-400'
                      : 'bg-amber-500/15 text-amber-300'
                  }`}>
                    {p.status === 'APPROVED' ? 'تأیید شده' : p.status === 'REJECTED' ? 'رد شده' : 'در انتظار بررسی'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
