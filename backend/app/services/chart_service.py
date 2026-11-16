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
os.makedirs(AUTO_CHARTS_DIR, exist_ok=True)
os.makedirs(CUSTOM_CHARTS_DIR, exist_ok=True)


class ChartService:
    """Service handling mplfinance chart generation and secure image upload sanitization."""

    @classmethod
    def _render_mplfinance_sync(
        cls,
        df: pd.DataFrame,
        entry: float,
        sl: Optional[float],
        tp: Optional[float],
        symbol: str,
        timeframe: str,
        output_path: str
    ) -> str:
        """Synchronous CPU-bound chart renderer designed to run in asyncio.to_thread."""
        try:
            # Custom dark trading theme matching App.jsx (#0b0f19)
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

            hlines_dict = {}
            hlines_colors = []
            hlines_styles = []

            # Entry line (Blue solid)
            hlines_vals = [entry]
            hlines_colors.append("#3b82f6")
            hlines_styles.append("-")

            # Stop Loss (Red dashed)
            if sl and sl > 0:
                hlines_vals.append(sl)
                hlines_colors.append("#ef4444")
                hlines_styles.append("--")

            # Take Profit (Green dashed)
            if tp and tp > 0:
                hlines_vals.append(tp)
                hlines_colors.append("#22c55e")
                hlines_styles.append("--")

            hlines_dict = {
                "hlines": hlines_vals,
                "colors": hlines_colors,
                "linestyle": hlines_styles,
                "linewidths": 1.2
            }

            fig, axlist = mpf.plot(
                df,
                type="candle",
                style=custom_style,
                title=f"\n{symbol} - {timeframe} Snapshot",
                hlines=hlines_dict,
                volume=False,
                figsize=(8.0, 4.5),
                tight_layout=True,
                returnfig=True
            )

            fig.savefig(output_path, dpi=120, facecolor="#0b0f19", edgecolor="none")
            return output_path
        finally:
            # Crucial rule: prevent memory leaks by closing all matplotlib figures
            plt.close("all")

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
        """Asynchronously renders and saves an mplfinance candlestick chart."""
        filename = f"{trade_id}_{timeframe}.png"
        filepath = os.path.join(AUTO_CHARTS_DIR, filename)

        await asyncio.to_thread(
            cls._render_mplfinance_sync,
            df,
            entry,
            sl,
            tp,
            symbol,
            timeframe,
            filepath
        )

        relative_url = f"/static/charts_auto/{filename}"
        logger.info(f"Generated auto chart for trade {trade_id} at {relative_url}")
        return relative_url

    @classmethod
    def _sanitize_and_save_image_sync(cls, file_bytes: bytes, target_path: str) -> str:
        """Sanitizes image format, strips EXIF, resizes, and saves as WebP."""
        try:
            stream = io.BytesIO(file_bytes)
            with Image.open(stream) as img:
                # 1. Format validation
                if img.format not in ["JPEG", "PNG", "WEBP"]:
                    raise BusinessValidationError("فرمت تصویر نامعتبر است. فقط JPG، PNG یا WEBP مجاز می‌باشد.")

                # 2. Convert to RGB to strip EXIF and transparent color profiles
                rgb_img = img.convert("RGB")

                # 3. Proportionally resize thumbnail if larger than 1600x1600
                rgb_img.thumbnail((1600, 1600), Image.Resampling.LANCZOS)

                # 4. Save optimized WebP image
                rgb_img.save(target_path, "WEBP", quality=85, optimize=True)
                return target_path
        except BusinessValidationError:
            raise
        except Exception as e:
            raise BusinessValidationError(f"پردازش و اعتبارسنجی فایل تصویر با خطا مواجه شد: {e}")

    @classmethod
    async def process_custom_chart_upload(cls, file_bytes: bytes, previous_image_url: Optional[str] = None) -> str:
        """Validates payload size, strips metadata, saves to storage, and cleans up previous file."""
        max_mb = DynamicConfig.get("max_chart_upload_mb", 2.0)
        max_bytes = int(max_mb * 1024 * 1024)
        if len(file_bytes) > max_bytes:
            raise BusinessValidationError(f"حجم فایل بیش از سقف مجاز ({max_mb} مگابایت) است.")

        filename = f"{uuid.uuid4().hex}.webp"
        filepath = os.path.join(CUSTOM_CHARTS_DIR, filename)

        await asyncio.to_thread(cls._sanitize_and_save_image_sync, file_bytes, filepath)

        # Cleanup old custom file from disk if exists
        if previous_image_url and "charts_custom" in previous_image_url:
            old_filename = os.path.basename(previous_image_url)
            old_path = os.path.join(CUSTOM_CHARTS_DIR, old_filename)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    logger.debug(f"Removed previous custom chart: {old_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete old chart file {old_path}: {e}")

        relative_url = f"/static/charts_custom/{filename}"
        return relative_url

    @classmethod
    def remove_chart_file(cls, chart_url: Optional[str]) -> None:
        """Deletes chart file from storage if present."""
        if not chart_url:
            return
        filename = os.path.basename(chart_url)
        if "charts_custom" in chart_url:
            path = os.path.join(CUSTOM_CHARTS_DIR, filename)
        else:
            path = os.path.join(AUTO_CHARTS_DIR, filename)

        if os.path.exists(path):
            try:
                os.remove(path)
                logger.info(f"Deleted chart file: {path}")
            except Exception as e:
                logger.warning(f"Error removing chart file {path}: {e}")
