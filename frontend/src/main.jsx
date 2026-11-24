import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

// Notify Telegram WebApp that the app is ready and expand viewport
if (typeof window !== "undefined" && window.Telegram?.WebApp) {
  try {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
  } catch (e) {
    // Ignore outside Telegram
  }
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 text-white flex flex-col items-center justify-center p-6 text-center">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center text-3xl mb-4">
            ⚠️
          </div>
          <h2 className="text-xl font-bold mb-2">خطا در بارگذاری برنامه</h2>
          <p className="text-sm text-gray-400 mb-6 max-w-xs">
            {this.state.error?.message || "مشکلی در اجرای رابط کاربری رخ داده است."}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm transition-colors shadow-lg shadow-blue-500/20"
          >
            تلاش مجدد
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
