#!/usr/bin/env python
"""Telegram bot for searching music in high quality and FLAC."""

import asyncio
import logging
import os
from importlib import resources

from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from flacbot.search import search_music

logger = logging.getLogger(__name__)

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_BOT_API = os.getenv("TG_BOT_API", "https://api.telegram.org")


def get_help_text() -> str:
    """Load help text from resources."""
    return resources.files("flacbot").joinpath("texts").joinpath("help.tg.md").read_text(encoding="UTF-8")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(get_help_text(), parse_mode="Markdown", disable_web_page_preview=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    await update.message.reply_text(get_help_text(), parse_mode="Markdown", disable_web_page_preview=True)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search <query> command."""
    query = " ".join(context.args) if context.args else ""
    if not query.strip():
        await update.message.reply_text(
            "Введите запрос для поиска. Пример:\n`/search Queen Bohemian Rhapsody`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(f"🔍 Ищу: _{query}_...", parse_mode="Markdown")
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, search_music, query)
        if not results:
            await update.message.reply_text("Ничего не найдено. Попробуйте другой запрос.")
            return

        # Format and send results (max 10 to avoid message overflow)
        lines = []
        for i, track in enumerate(results[:10], 1):
            artist = track.get("artist", "?")
            title = track.get("title", "?")
            album = track.get("album", "")
            quality = track.get("quality", "")
            links = track.get("links", {})

            line = f"**{i}. {artist} — {title}**"
            if album:
                line += f"\n   📀 {album}"
            if quality:
                line += f"\n   🎵 {quality}"
            link_str = " | ".join(f"[{k}]({v})" for k, v in list(links.items())[:5]) if links else ""
            if link_str:
                line += f"\n   🔗 {link_str}"
            lines.append(line)

        text = "\n\n".join(lines)
        if len(text) > 4000:
            text = text[:3950] + "\n\n_...результаты обрезаны_"
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Search failed: %s", e)
        await update.message.reply_text(f"Ошибка поиска: {e}")


async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text search (when message is not a command)."""
    query = (update.message.text or "").strip()
    if not query or len(query) < 2:
        return

    await update.message.reply_text(f"🔍 Ищу: _{query}_...", parse_mode="Markdown")
    try:
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, search_music, query)
        if not results:
            await update.message.reply_text("Ничего не найдено.")
            return

        lines = []
        for i, track in enumerate(results[:5], 1):
            artist = track.get("artist", "?")
            title = track.get("title", "?")
            links = track.get("links", {})
            link_str = " | ".join(f"[{k}]({v})" for k, v in list(links.items())[:4]) if links else ""
            lines.append(f"**{i}. {artist} — {title}**\n{link_str}")

        text = "\n\n".join(lines)
        if len(text) > 4000:
            text = text[:3950] + "\n\n_..._"
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Search failed: %s", e)
        await update.message.reply_text(f"Ошибка: {e}")


def main() -> None:
    """Run the bot."""
    if not TG_BOT_TOKEN:
        raise SystemExit("Set TG_BOT_TOKEN environment variable")

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=os.getenv("LOGLEVEL", "INFO").upper(),
    )

    application = (
        ApplicationBuilder()
        .token(TG_BOT_TOKEN)
        .base_url(f"{TG_BOT_API}/bot")
        .base_file_url(f"{TG_BOT_API}/file/bot")
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
