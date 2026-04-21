import os
import feedparser
import asyncio
import logging
import re
from datetime import datetime, timezone
from telegram import Bot
from telegram.constants import ParseMode
import schedule
import time

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

RSS_FEEDS = {
    "🌍 International": "https://www.lemonde.fr/international/rss_full.xml",
    "💶 Économie": "https://www.lemonde.fr/economie/rss_full.xml",
    "🌿 Planète": "https://www.lemonde.fr/planete/rss_full.xml",
    "🏛️ Politique": "https://www.lemonde.fr/politique/rss_full.xml",
}

MAX_ARTICLES_PER_FEED = 3
SEND_TIMES = ["07:00", "12:00", "19:00"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

sent_links: set = set()

def fetch_articles(feed_url: str, max_count: int) -> list:
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:max_count * 2]:
            link = entry.get("link", "")
            if link in sent_links:
                continue
            title = entry.get("title", "Sans titre").strip()
            summary = entry.get("summary", "")
            summary = re.sub(r"<[^>]+>", "", summary).strip()
            summary = summary[:200] + "…" if len(summary) > 200 else summary
            articles.append({"title": title, "link": link, "summary": summary})
            if len(articles) >= max_count:
                break
        return articles
    except Exception as e:
        log.error(f"Erreur RSS {feed_url}: {e}")
        return []

def build_message() -> str:
    now = datetime.now(timezone.utc)
    heure = now.strftime("%H:%M")
    date = now.strftime("%d/%m/%Y")

    lines = [
        "📰 *Résumé de l'actualité mondiale*",
        f"🕐 {heure} UTC — {date}",
        "",
    ]

    total_articles = 0

    for rubrique, url in RSS_FEEDS.items():
        articles = fetch_articles(url, MAX_ARTICLES_PER_FEED)
        if not articles:
            continue

        lines.append(f"*{rubrique}*")
        for art in articles:
            title = art["title"].replace("*", "\\*").replace("_", "\\_")
            summary = art["summary"].replace("*", "\\*").replace("_", "\\_")
            link = art["link"]
            lines.append(f"• [{title}]({link})")
            if summary:
                lines.append(f"  _{summary}_")
            sent_links.add(link)
            total_articles += 1
        lines.append("")

    if total_articles == 0:
        return ""

    lines.append("_Source : Le Monde_")
    return "\n".join(lines)

async def send_digest():
    log.info("Génération du digest…")
    message = build_message()
    if not message:
        log.warning("Aucun nouvel article à envoyer.")
        return

    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False,
        )
        log.info("✅ Digest envoyé dans le canal.")
    except Exception as e:
        log.error(f"Erreur envoi Telegram : {e}")

def run_digest():
    asyncio.run(send_digest())

def start_scheduler():
    for t in SEND_TIMES:
        schedule.every().day.at(t).do(run_digest)
        log.info(f"📅 Digest planifié à {t} UTC")

    log.info("⏳ Bot en attente des prochains envois…")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    log.info("🚀 Démarrage du bot News Le Monde")
    run_digest()
    start_scheduler()
