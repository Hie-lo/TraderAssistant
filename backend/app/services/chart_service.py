import os
import io
import uuid
import asyncio
from typing import Optional
from decimal import Decimal

# Zero-Defect Rule: Agg backend must be set before any pyplot import
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
from PIL import Image

from app.core.config import settings
from app.core.dynamic_config import DynamicConfig
from app.core.exceptions import BusinessValidationError
from app.core.logger import logger

# Ensure storage directories exist
AUTO_CHARTS_DIR = os.path.join(settings.STORAGE_DIR, "charts_auto")
CUSTOM_CHARTS_DIR = os.path.join(settings.STORAGE_DIR, "charts_custom")
RECEIPTS_DIR = os.path.join(settings.STORAGE_DIR, "receipts")
os.makedirs(AUTO_CHARTS_DIR, exist_ok=True)
os.makedirs(CUSTOM_CHARTS_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


class ChartService:
    """Service handling mplfinance chart generation (in-memory BytesIO first) and image sanitization."""

    @classmethod
    def _render_mplfinance_bytes_sync(
        cls,
        df: pd.DataFrame,
        entry: float,
        sl: Optional[float],
        tp: Optional[float],
        symbol: str,
        timeframe: str,
    ) -> bytes:
        """Synchronous CPU-bound chart renderer writing PNG strictly into an in-memory BytesIO buffer."""
        try:
            custom_colors = mpf.make_marketcolors(
                up="#10b981",
                down="#f43f5e",
                edge="inherit",
                wick="inherit",
                volume="#3b82f6"
            )
            custom_style = mpf.make_mpf_style(
                base_mpf_style="nightclouds",
                marketcolors=custom_colors,
                facecolor="#0b0f19",
                edgecolor="#1e293b",
                figcolor="#0b0f19",
                gridcolor="#1e293b",
                gridstyle="--",
                rc={"font.size": 8, "axes.labelsize": 8}
            )

            # Strictly use mpf.make_addplot for exact horizontal Entry / SL / TP lines across the chart
            addplots = [
                mpf.make_addplot(
                    pd.Series([entry] * len(df), index=df.index),
                    color="#3b82f6",
                    linestyle="-",
                    width=1.4,
                    secondary_y=False,
                )
            ]
            if sl and sl > 0:
                addplots.append(
                    mpf.make_addplot(
                        pd.Series([sl] * len(df), index=df.index),
                        color="#ef4444",
                        linestyle="--",
                        width=1.3,
                        secondary_y=False,
                    )
                )
            if tp and tp > 0:
                addplots.append(
                    mpf.make_addplot(
                        pd.Series([tp] * len(df), index=df.index),
                        color="#22c55e",
                        linestyle="--",
                        width=1.3,
                        secondary_y=False,
                    )
                )

            fig, axlist = mpf.plot(
                df,
                type="candle",
                style=custom_style,
                title=f"\n{symbol} - {timeframe} Snapshot",
                addplot=addplots,
                volume=False,
                figsize=(8.0, 4.5),
                tight_layout=True,
                returnfig=True
            )

            ax = axlist[0]
            ax.axhline(y=entry, color="#3b82f6", linewidth=0.4, alpha=0.0)  # keeps axis scaled
            legend_parts = [f"Entry: {entry:g}"]
            if sl and sl > 0:
                legend_parts.append(f"SL: {sl:g}")
            if tp and tp > 0:
                legend_parts.append(f"TP: {tp:g}")
            ax.set_xlabel("  |  ".join(legend_parts), color="#94a3b8", fontsize=8)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=120, facecolor="#0b0f19", edgecolor="none")
            buf.seek(0)
            return buf.getvalue()
        finally:
            plt.close("all")

    @classmethod
    async def render_chart_bytes(
        cls,
        symbol: str,
        timeframe: str,
        entry: float,
        sl: Optional[float],
        tp: Optional[float],
        df: pd.DataFrame
    ) -> bytes:
        """Generates candlestick PNG bytes strictly in memory without touching disk."""
        return await asyncio.to_thread(
            cls._render_mplfinance_bytes_sync,
            df,
            entry,
            sl,
            tp,
            symbol,
            timeframe
        )

    @classmethod
    async def generate_trade_chart(
        cls,
        trade_id: str,
        symbol: str,
        timeframe: str,
        entry: float,
        sl: Optional[float],
        tp: Optional[float],
        df: pd.DataFrame
    ) -> str:
        """Renders mplfinance chart in memory via BytesIO and persists to disk only for saved trades."""
        png_bytes = await cls.render_chart_bytes(
            symbol=symbol,
            timeframe=timeframe,
            entry=entry,
            sl=sl,
            tp=tp,
            df=df
        )

        filename = f"{trade_id}_{timeframe}.png"
        filepath = os.path.join(AUTO_CHARTS_DIR, filename)

        def _write_bytes() -> None:
            with open(filepath, "wb") as f:
                f.write(png_bytes)

        await asyncio.to_thread(_write_bytes)

        relative_url = f"/static/charts_auto/{filename}"
        logger.info(f"Generated auto chart for trade {trade_id} at {relative_url}")
        return relative_url

    @classmethod
    def _sanitize_and_save_image_sync(cls, file_bytes: bytes, target_path: str) -> str:
        """Sanitizes image format, strips EXIF, resizes, and saves as WebP."""
        try:
            stream = io.BytesIO(file_bytes)
            with Image.open(stream) as img:
                if img.format not in ["JPEG", "PNG", "WEBP"]:
                    raise BusinessValidationError("فرمت تصویر نامعتبر است. فقط JPG، PNG یا WEBP مجاز می‌باشد.")

                rgb_img = img.convert("RGB")
                rgb_img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                rgb_img.save(target_path, "WEBP", quality=85, optimize=True)
                return target_path
        except BusinessValidationError:
            raise
        except Exception as e:
            raise BusinessValidationError(f"پردازش و اعتبارسنجی فایل تصویر با خطا مواجه شد: {e}")

    @classmethod
    async def _process_image_upload(
        cls,
        file_bytes: bytes,
        target_dir: str,
        static_subpath: str,
        previous_image_url: Optional[str] = None,
    ) -> str:
        max_mb = DynamicConfig.get("max_chart_upload_mb", 2.0)
        max_bytes = int(max_mb * 1024 * 1024)
        if len(file_bytes) > max_bytes:
            raise BusinessValidationError(f"حجم فایل بیش از سقف مجاز ({max_mb} مگابایت) است.")

        filename = f"{uuid.uuid4().hex}.webp"
        filepath = os.path.join(target_dir, filename)
        await asyncio.to_thread(cls._sanitize_and_save_image_sync, file_bytes, filepath)

        if previous_image_url and static_subpath in previous_image_url:
            old_path = os.path.join(target_dir, os.path.basename(previous_image_url))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    logger.warning(f"Failed to delete old upload file {old_path}: {e}")

        return f"/static/{static_subpath}/{filename}"

    @classmethod
    async def process_custom_chart_upload(cls, file_bytes: bytes, previous_image_url: Optional[str] = None) -> str:
        """Validates payload size, strips metadata, saves chart to storage, and cleans up previous file."""
        return await cls._process_image_upload(file_bytes, CUSTOM_CHARTS_DIR, "charts_custom", previous_image_url)

    @classmethod
    async def process_receipt_upload(cls, file_bytes: bytes) -> str:
        """Validates and sanitizes VIP payment receipt image and stores under /static/receipts/."""
        return await cls._process_image_upload(file_bytes, RECEIPTS_DIR, "receipts")

    @classmethod
    def remove_chart_file(cls, chart_url: Optional[str]) -> None:
        """Deletes chart file from storage if present."""
        if not chart_url:
            return
        filename = os.path.basename(chart_url)
        if "charts_custom" in chart_url:
            path = os.path.join(CUSTOM_CHARTS_DIR, filename)
        elif "receipts" in chart_url:
            path = os.path.join(RECEIPTS_DIR, filename)
        else:
            path = os.path.join(AUTO_CHARTS_DIR, filename)

        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Deleted image file: {path}")
            except Exception as e:
                logger.warning(f"Error removing image file {path}: {e}")
