import React, { useState, useEffect } from 'react';
import { api } from '../api/client';

const formatDateFa = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('fa-IR');
  } catch {
    return iso.slice(0, 10);
  }
};

export default function AdminCustomerPanel({
  channelTemplate,
  setChannelTemplate,
  channelIdInput,
  setChannelIdInput,
  isLoadingTemplate,
  isSavingTemplate,
  templateFeedback,
  onSaveTemplate,
}) {
  const [subTab, setSubTab] = useState('payments'); // 'payments' | 'users' | 'settings'
  const [payments, setPayments] = useState([]);
  const [paymentFilter, setPaymentFilter] = useState('PENDING');
  const [loadingPayments, setLoadingPayments] = useState(false);
  const [receiptZoomUrl, setReceiptZoomUrl] = useState(null);

  const [users, setUsers] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [editingVipUser, setEditingVipUser] = useState(null);
  const [vipDaysInput, setVipDaysInput] = useState('30');
  const [vipExactDateInput, setVipExactDateInput] = useState('');

  const [cardNumber, setCardNumber] = useState('');
  const [cardName, setCardName] = useState('');
  const [price1m, setPrice1m] = useState('290000');
  const [price3m, setPrice3m] = useState('750000');
  const [price6m, setPrice6m] = useState('1350000');
  const [adminToast, setAdminToast] = useState(null);

  const loadPayments = async (filterVal = paymentFilter) => {
    setLoadingPayments(true);
    try {
      const list = await api.getAdminPayments(filterVal);
      setPayments(Array.isArray(list) ? list : []);
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    } finally {
      setLoadingPayments(false);
    }
  };

  const loadUsers = async () => {
    setLoadingUsers(true);
    try {
      const list = await api.getAdminUsers();
      setUsers(Array.isArray(list) ? list : []);
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadVipConfig = async () => {
    try {
      const res = await api.getVipPlans();
      setCardNumber(res.adminCardNumber || '');
      setCardName(res.adminCardName || '');
      const prices = res.vipPrices || {};
      setPrice1m(String(prices['1'] ?? prices[1] ?? 290000));
      setPrice3m(String(prices['3'] ?? prices[3] ?? 750000));
      setPrice6m(String(prices['6'] ?? prices[6] ?? 1350000));
    } catch (err) {
      console.warn('Failed to load VIP config:', err);
    }
  };

  useEffect(() => {
    if (subTab === 'payments') loadPayments(paymentFilter);
    else if (subTab === 'users') loadUsers();
    else if (subTab === 'settings') loadVipConfig();
  }, [subTab, paymentFilter]);

  const handlePaymentDecision = async (paymentId, approve) => {
    setAdminToast(null);
    try {
      if (approve) {
        await api.approveAdminPayment(paymentId);
        setAdminToast({ type: 'success', msg: `فیش #${paymentId} تأیید و اشتراک VIP کاربر فعال شد.` });
      } else {
        await api.rejectAdminPayment(paymentId);
        setAdminToast({ type: 'success', msg: `فیش #${paymentId} رد شد.` });
      }
      loadPayments(paymentFilter);
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    }
  };

  const handleBanToggle = async (u) => {
    const nextStatus = u.status === 'BANNED' ? 'ACTIVE' : 'BANNED';
    setAdminToast(null);
    try {
      await api.updateAdminUserStatus(u.id, {
        status: nextStatus,
        banReason: nextStatus === 'BANNED' ? 'مسدودسازی توسط مدیر سیستم' : null,
      });
      setUsers((prev) => prev.map((row) => (row.id === u.id ? { ...row, status: nextStatus } : row)));
      setAdminToast({ type: 'success', msg: `وضعیت کاربر ${u.firstName} به ${nextStatus} تغییر یافت.` });
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    }
  };

  const handleManualVipSubmit = async (action, extra = {}) => {
    if (!editingVipUser) return;
    setAdminToast(null);
    try {
      const res = await api.manualEditUserVip(editingVipUser.id, {
        action,
        days: extra.days ?? (parseInt(vipDaysInput, 10) || 0),
        exactDate: extra.exactDate ?? vipExactDateInput,
        role: extra.role,
      });
      setUsers((prev) =>
        prev.map((row) =>
          row.id === editingVipUser.id
            ? { ...row, role: res.role, subscriptionEndDate: res.subscriptionEndDate }
            : row
        )
      );
      setEditingVipUser((prev) =>
        prev ? { ...prev, role: res.role, subscriptionEndDate: res.subscriptionEndDate } : null
      );
      setAdminToast({ type: 'success', msg: `اشتراک VIP کاربر ${editingVipUser.firstName} به‌روزرسانی شد.` });
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    }
  };

  const handleSaveVipPricing = async () => {
    setAdminToast(null);
    try {
      await api.updateVipSettings({
        adminCardNumber: cardNumber,
        adminCardName: cardName,
        vipPrices: {
          '1': Number(price1m) || 290000,
          '3': Number(price3m) || 750000,
          '6': Number(price6m) || 1350000,
        },
      });
      setAdminToast({ type: 'success', msg: 'اطلاعات کارت بانکی و تعرفه‌های VIP ذخیره شدند.' });
    } catch (err) {
      setAdminToast({ type: 'error', msg: err.message });
    }
  };

  const filteredUsers = users.filter((u) => {
    const q = userSearch.trim().toLowerCase();
    if (!q) return true;
    return (
      String(u.id).includes(q) ||
      (u.firstName || '').toLowerCase().includes(q) ||
      (u.username || '').toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-3.5 sm:p-5 flex-1 min-h-0 overflow-y-auto overflow-x-hidden space-y-4 pb-6">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
        <div>
          <h2 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
            🛡️ پنل مدیریت مشتریان و انتشار
          </h2>
          <span className="text-[10px] sm:text-xs text-gray-400">تأیید پرداخت‌های VIP، مدیریت کاربران و قالب کانال</span>
        </div>
        <span className="bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 px-2.5 py-1 rounded-xl text-[10px] sm:text-xs font-mono font-bold">
          ADMIN
        </span>
      </div>

      {/* Admin Sub-Navigation */}
      <div className="grid grid-cols-3 gap-1.5 bg-gray-950 p-1 rounded-xl border border-gray-800">
        {[
          { id: 'payments', label: '💳 فیش‌های VIP' },
          { id: 'users', label: '👥 کاربران' },
          { id: 'settings', label: '⚙️ قالب و تعرفه' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => { setSubTab(tab.id); setAdminToast(null); }}
            className={`py-2 rounded-lg text-[11px] sm:text-xs font-bold transition-all ${
              subTab === tab.id
                ? 'bg-indigo-600 text-white shadow'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {adminToast && (
        <div className={`text-xs px-3 py-2.5 rounded-xl border flex items-center justify-between gap-2 ${
          adminToast.type === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
        }`}>
          <span>{adminToast.msg}</span>
          <button type="button" onClick={() => setAdminToast(null)} className="px-1">✕</button>
        </div>
      )}

      {/* ==================== SUB-TAB 1: PENDING PAYMENTS ==================== */}
      {subTab === 'payments' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-bold text-gray-300">لیست فیش‌های واریزی</span>
            <div className="flex bg-gray-950 p-0.5 rounded-lg border border-gray-800 text-[10px]">
              {['PENDING', 'ALL'].map((st) => (
                <button
                  key={st}
                  type="button"
                  onClick={() => setPaymentFilter(st)}
                  className={`px-2.5 py-1 rounded-md font-bold ${
                    paymentFilter === st ? 'bg-indigo-600 text-white' : 'text-gray-400'
                  }`}
                >
                  {st === 'PENDING' ? 'در انتظار' : 'همه'}
                </button>
              ))}
            </div>
          </div>

          {loadingPayments ? (
            <div className="text-center text-xs text-gray-500 py-6">در حال بارگذاری...</div>
          ) : payments.length === 0 ? (
            <div className="bg-gray-950/70 border border-dashed border-gray-800 rounded-xl p-6 text-center text-xs text-gray-500">
              فیش واریزی در این بخش وجود ندارد.
            </div>
          ) : (
            <div className="space-y-2.5">
              {payments.map((p) => (
                <div key={p.id} className="bg-gray-950 border border-gray-800 rounded-xl p-3 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-xs font-bold text-white flex items-center gap-1.5">
                        <span>{p.firstName}</span>
                        {p.username && <span className="text-[10px] text-gray-400 font-mono">@{p.username}</span>}
                        <span className="text-[10px] bg-amber-500/15 text-amber-300 px-1.5 py-0.5 rounded">
                          پلن {p.planDuration} ماهه
                        </span>
                      </div>
                      <span className="text-[10px] text-gray-500 font-mono block mt-0.5">
                        ID: {p.userId} • {p.createdAt}
                      </span>
                    </div>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      p.status === 'APPROVED'
                        ? 'bg-emerald-500/15 text-emerald-400'
                        : p.status === 'REJECTED'
                        ? 'bg-rose-500/15 text-rose-400'
                        : 'bg-amber-500/15 text-amber-300'
                    }`}>
                      {p.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setReceiptZoomUrl(p.receiptImageUrl)}
                      className="px-2.5 py-1.5 rounded-lg bg-gray-900 hover:bg-gray-800 border border-gray-700 text-[11px] text-blue-300 font-bold"
                    >
                      🖼️ مشاهده فیش
                    </button>
                    {p.status === 'PENDING' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handlePaymentDecision(p.id, true)}
                          className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold"
                        >
                          ✓ تأیید و VIP
                        </button>
                        <button
                          type="button"
                          onClick={() => handlePaymentDecision(p.id, false)}
                          className="px-3 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/35 border border-rose-500/30 text-rose-300 text-[11px] font-bold"
                        >
                          ✕ رد فیش
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {receiptZoomUrl && (
            <div
              onClick={() => setReceiptZoomUrl(null)}
              className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4"
            >
              <div onClick={(e) => e.stopPropagation()} className="max-w-md w-full bg-gray-900 border border-gray-700 rounded-2xl p-3 space-y-2">
                <div className="flex justify-between items-center text-xs font-bold text-white">
                  <span>تصویر فیش واریزی</span>
                  <button type="button" onClick={() => setReceiptZoomUrl(null)} className="px-2 py-0.5 bg-gray-800 rounded">✕</button>
                </div>
                <img src={receiptZoomUrl} alt="Payment Receipt" className="w-full max-h-[70vh] object-contain rounded-xl bg-black" />
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== SUB-TAB 2: USER DIRECTORY & MANUAL VIP EDIT ==================== */}
      {subTab === 'users' && (
        <div className="space-y-3">
          <input
            type="text"
            value={userSearch}
            onChange={(e) => setUserSearch(e.target.value)}
            placeholder="جستجو بر اساس نام، یوزرنیم یا آیدی عددی..."
            className="w-full bg-gray-950 border border-gray-800 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs text-white outline-none"
          />

          {loadingUsers ? (
            <div className="text-center text-xs text-gray-500 py-6">در حال بارگذاری کاربران...</div>
          ) : (
            <div className="space-y-2">
              {filteredUsers.map((u) => (
                <div key={u.id} className="bg-gray-950 border border-gray-800 rounded-xl p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-white flex flex-wrap items-center gap-1.5">
                        <span>{u.firstName}</span>
                        {u.username && <span className="text-[10px] font-mono text-gray-400">@{u.username}</span>}
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                          u.role === 'ADMIN'
                            ? 'bg-indigo-500/20 text-indigo-300'
                            : u.role === 'VIP'
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-gray-800 text-gray-400'
                        }`}>
                          {u.role}
                        </span>
                        {u.status === 'BANNED' && (
                          <span className="text-[10px] bg-rose-500/20 text-rose-400 px-1.5 py-0.5 rounded">BANNED</span>
                        )}
                      </div>
                      <span className="text-[10px] text-gray-500 font-mono block mt-0.5">
                        ID: {u.id} • معاملات: {u.tradesCount} • انقضا VIP: {formatDateFa(u.subscriptionEndDate)}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingVipUser(u);
                          setVipExactDateInput(u.subscriptionEndDate ? u.subscriptionEndDate.slice(0, 10) : '');
                        }}
                        className="px-2.5 py-1.5 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[10px] font-bold"
                      >
                        👑 ویرایش دستی VIP
                      </button>
                      {u.role !== 'ADMIN' && (
                        <button
                          type="button"
                          onClick={() => handleBanToggle(u)}
                          className={`px-2.5 py-1.5 rounded-lg text-[10px] font-bold border ${
                            u.status === 'BANNED'
                              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
                              : 'bg-rose-500/15 border-rose-500/30 text-rose-300'
                          }`}
                        >
                          {u.status === 'BANNED' ? 'رفع مسدودی' : 'مسدود'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Manual VIP Edit Modal */}
          {editingVipUser && (
            <div
              onClick={() => setEditingVipUser(null)}
              className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
            >
              <div onClick={(e) => e.stopPropagation()} className="w-full max-w-sm bg-gray-900 border border-amber-500/30 rounded-2xl p-4 space-y-3">
                <div className="flex items-center justify-between border-b border-gray-800 pb-2">
                  <span className="text-xs sm:text-sm font-extrabold text-white">
                    👑 ویرایش دستی VIP: {editingVipUser.firstName}
                  </span>
                  <button type="button" onClick={() => setEditingVipUser(null)} className="text-gray-400 hover:text-white px-1">✕</button>
                </div>

                <div className="text-[11px] text-gray-400 bg-gray-950 p-2.5 rounded-xl border border-gray-800">
                  نقش فعلی: <b className="text-amber-300">{editingVipUser.role}</b> | انقضا: <b className="text-white">{formatDateFa(editingVipUser.subscriptionEndDate)}</b>
                </div>

                {/* Add / Subtract Days */}
                <div className="space-y-1.5">
                  <label className="text-[11px] text-gray-300 font-bold block">افزودن یا کسر روز اشتراک:</label>
                  <div className="flex gap-1.5">
                    <input
                      dir="ltr"
                      type="number"
                      value={vipDaysInput}
                      onChange={(e) => setVipDaysInput(e.target.value)}
                      className="w-20 bg-gray-950 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-center font-mono text-white"
                    />
                    <button
                      type="button"
                      onClick={() => handleManualVipSubmit('add_days')}
                      className="flex-1 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold"
                    >
                      + افزودن روز
                    </button>
                    <button
                      type="button"
                      onClick={() => handleManualVipSubmit('sub_days')}
                      className="flex-1 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/35 border border-rose-500/30 text-rose-300 text-xs font-bold"
                    >
                      - کسر روز
                    </button>
                  </div>
                </div>

                {/* Exact Expiration Date */}
                <div className="space-y-1.5">
                  <label className="text-[11px] text-gray-300 font-bold block">تنظیم تاریخ دقیق انقضا:</label>
                  <div className="flex gap-1.5">
                    <input
                      dir="ltr"
                      type="date"
                      value={vipExactDateInput}
                      onChange={(e) => setVipExactDateInput(e.target.value)}
                      className="flex-1 bg-gray-950 border border-gray-700 rounded-lg px-2 py-1.5 text-xs font-mono text-white"
                    />
                    <button
                      type="button"
                      onClick={() => handleManualVipSubmit('set_date')}
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold"
                    >
                      اعمال تاریخ
                    </button>
                  </div>
                </div>

                {/* Role & Revoke */}
                <div className="grid grid-cols-3 gap-1.5 pt-1 border-t border-gray-800">
                  <button
                    type="button"
                    onClick={() => handleManualVipSubmit('add_days', { days: 30 })}
                    className="py-1.5 rounded-lg bg-amber-500/20 text-amber-300 text-[10px] font-bold"
                  >
                    هدیه ۳۰ روزه
                  </button>
                  <button
                    type="button"
                    onClick={() => handleManualVipSubmit('set_role', { role: 'ADMIN' })}
                    className="py-1.5 rounded-lg bg-indigo-500/20 text-indigo-300 text-[10px] font-bold"
                  >
                    ارتقا به ADMIN
                  </button>
                  <button
                    type="button"
                    onClick={() => handleManualVipSubmit('revoke')}
                    className="py-1.5 rounded-lg bg-gray-800 text-gray-300 text-[10px] font-bold"
                  >
                    بازگشت به رایگان
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================== SUB-TAB 3: VIP PRICING & CHANNEL TEMPLATE ==================== */}
      {subTab === 'settings' && (
        <div className="space-y-4">
          {/* VIP Card & Pricing Card */}
          <div className="bg-gray-950 border border-gray-800 rounded-2xl p-3.5 sm:p-4 space-y-3">
            <h3 className="text-xs font-extrabold text-amber-300">💳 تنظیمات کارت بانکی و تعرفه اشتراک VIP</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label className="text-[10px] text-gray-400 block mb-1">شماره کارت ادمین</label>
                <input
                  dir="ltr"
                  type="text"
                  value={cardNumber}
                  onChange={(e) => setCardNumber(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs font-mono text-white outline-none focus:border-amber-500"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 block mb-1">نام صاحب کارت</label>
                <input
                  type="text"
                  value={cardName}
                  onChange={(e) => setCardName(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-amber-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="text-[10px] text-gray-400 block mb-1">قیمت ۱ ماهه (تومان)</label>
                <input
                  dir="ltr"
                  type="number"
                  value={price1m}
                  onChange={(e) => setPrice1m(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-2.5 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 block mb-1">قیمت ۳ ماهه (تومان)</label>
                <input
                  dir="ltr"
                  type="number"
                  value={price3m}
                  onChange={(e) => setPrice3m(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-2.5 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <label className="text-[10px] text-gray-400 block mb-1">قیمت ۶ ماهه (تومان)</label>
                <input
                  dir="ltr"
                  type="number"
                  value={price6m}
                  onChange={(e) => setPrice6m(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-2.5 py-1.5 text-xs font-mono text-white"
                />
              </div>
            </div>

            <button
              type="button"
              onClick={handleSaveVipPricing}
              className="w-full py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-gray-950 font-bold text-xs transition-colors"
            >
              ذخیره اطلاعات کارت و قیمت‌های VIP
            </button>
          </div>

          {/* Channel Post Jinja2 Template */}
          {isLoadingTemplate ? (
            <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 text-center text-xs text-gray-400">
              در حال بارگذاری قالب کانال...
            </div>
          ) : (
            <div className="space-y-3">
              <div className="bg-gray-950 border border-gray-800 rounded-2xl p-3.5 sm:p-4 space-y-2">
                <label className="text-xs font-bold text-gray-300 block">شناسه کانال مقصد (CHANNEL_ID)</label>
                <input
                  dir="ltr"
                  type="text"
                  value={channelIdInput}
                  onChange={(e) => setChannelIdInput(e.target.value)}
                  placeholder="-1001234567890 یا @my_trading_channel"
                  className="w-full bg-gray-900 border border-gray-700 focus:border-indigo-500 rounded-xl px-3 py-2 text-xs font-mono text-white outline-none"
                />
              </div>

              <div className="bg-gray-950 border border-gray-800 rounded-2xl p-3.5 sm:p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-gray-300">قالب پست کانال (Jinja2 + HTML)</label>
                  <span className="text-[10px] text-gray-500 font-mono">Max 1024 chars</span>
                </div>
                <textarea
                  dir="ltr"
                  rows="6"
                  value={channelTemplate}
                  onChange={(e) => setChannelTemplate(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-700 focus:border-indigo-500 rounded-xl p-3 text-xs font-mono text-gray-100 outline-none leading-relaxed"
                />
                <div dir="ltr" className="flex flex-wrap gap-1.5">
                  {['{{ pair }}', '{{ direction }}', '{{ entry_price }}', '{{ sl }}', '{{ tp }}', '{{ leverage }}', '{{ rr }}', '{{ status }}', '{{ strategy }}', '{{ notes }}'].map((token) => (
                    <button
                      key={token}
                      type="button"
                      onClick={() => setChannelTemplate((prev) => `${prev}${prev && !prev.endsWith(' ') && !prev.endsWith('\n') ? ' ' : ''}${token}`)}
                      className="px-2 py-0.5 rounded-md bg-gray-900 hover:bg-indigo-600/25 border border-gray-800 text-[10px] font-mono text-indigo-300"
                    >
                      {token}
                    </button>
                  ))}
                </div>
              </div>

              {templateFeedback && (
                <div className={`text-xs px-3 py-2 rounded-xl border ${
                  templateFeedback.type === 'success'
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}>
                  {templateFeedback.msg}
                </div>
              )}

              <button
                type="button"
                onClick={onSaveTemplate}
                disabled={isSavingTemplate}
                className="w-full py-3 rounded-xl font-bold text-xs sm:text-sm bg-indigo-600 hover:bg-indigo-500 text-white"
              >
                {isSavingTemplate ? 'در حال ذخیره...' : 'ذخیره قالب انتشار کانال'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
