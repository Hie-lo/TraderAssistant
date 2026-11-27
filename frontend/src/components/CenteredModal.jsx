import React, { useEffect } from 'react';
import { X } from 'lucide-react';

const CenteredModal = ({ isOpen, onClose, title, subtitle, children }) => {
  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      dir="rtl"
      className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm max-h-[80vh] rounded-2xl border border-gray-800 bg-gray-900 shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 px-4 py-3 border-b border-gray-800 flex items-center justify-between gap-2 bg-gray-950/70">
          <div className="min-w-0">
            <h3 className="text-sm font-extrabold text-white truncate">{title}</h3>
            {subtitle && (
              <p className="text-[10px] text-gray-400 truncate mt-0.5">{subtitle}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="w-7 h-7 rounded-lg bg-gray-800/80 hover:bg-gray-700 text-gray-300 hover:text-white flex items-center justify-center transition-colors shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-3">
          {children}
        </div>
      </div>
    </div>
  );
};

export default CenteredModal;
