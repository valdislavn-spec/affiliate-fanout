# affiliate-fanout

[![tests](https://github.com/valdislavn-spec/affiliate-fanout/actions/workflows/tests.yml/badge.svg)](https://github.com/valdislavn-spec/affiliate-fanout/actions/workflows/tests.yml) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/valdislavn-spec/affiliate-fanout) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Публикация партнёрских ссылок во все бесплатные соцсети через API** — один
пост, везде свой `sub_id`, свой click-tracker и обязательное раскрытие
«реклама / партнёрская ссылка».

- **0 зависимостей** — только Python standard library (3.9+).
- **22 платформы**: Telegram, X (Twitter), Reddit, Pinterest, Facebook,
  Instagram, Threads, LinkedIn, Medium, Blogger, WordPress, Tumblr, Bluesky,
  Mastodon / Akkoma / Pixelfed, dev.to, Discord, Slack, Telegraph, Raindrop.
- **Travelpayouts**: на каждый канал создаётся своя партнёрская ссылка с
  `sub_id=<prefix>_<platform>` через Partner Links API.
- **Свой click-tracker**: ссылка оборачивается в `/r/<code>` для статистики
  кликов по платформам.
- **Безопасно по умолчанию**: dry-run, постинг только с `--execute`,
  раскрытие рекламы добавляется автоматически.
- **21 офлайн-тест** на stdlib `unittest` с мок-сервером всех API.

> Независимый open-source проект. Партнёрские ссылки нужно сопровождать
> раскрытием (FTC §255 «Endorsement Guides» / EU UCPD) — флаг `--disclosure`
> включён по умолчанию. Уважайте ToS платформ и правила сабреддитов/групп.

---

## Проверенные подключения (10.11.2026)

| Канал | Статус | Комментарий |
|---|---|---|
| Telegram Bot API (релей) | ✅ | бот настроен, 4 канала |
| Tumblr API v2 | ✅ | блог настроен |
| Bluesky (AT Protocol) | ✅ | app password |
| Akkoma | ✅ | |
| Pixelfed | ✅ | |
| Telegraph | ✅ | без авторизации |
| Свой click-tracker | ✅ | 23 ссылки, коды `fanout-*` |
| Travelpayouts Links API | ✅ | нужен `TRAVELPAYOUTS_TRS` |
| X (Twitter) API v2 | ⚠️ | код готов; нужны OAuth1-ключи приложения (free: 500 постов/мес) |
| Reddit API | ⚠️ | код готов; script-app + non-commercial (иначе бан) |
| Pinterest API v5 | ⚠️ | код готов; нужен approved app + image URL |
| Facebook / Instagram / Threads | ⚠️ | код готов; нужен Meta app review + токены |
| LinkedIn | ⚠️ | код готов; app + `w_member_social`, `LINKEDIN_AUTHOR_URN` |
| Medium | ⚠️ | legacy API: новые токены не выдают, старые работают |
| Blogger | ⚠️ | код готов; Google OAuth refresh token |
| WordPress | ⚠️ | self-hosted (app password) или WordPress.com (OAuth2) |
| dev.to, Discord, Slack, Raindrop | ⚠️ | код готов; нужны API key / webhook / токен |
| Mastodon | ❌ | текущий аккаунт отключён инстансом |

Проверить у себя: `python -m affiliate_fanout --env .env --verify`

Готовые ссылки под каждую платформу (партнёрская ссылка + tracker-код)
создаются в `local/links-ready.json` (каталог в `.gitignore`).

---

## Быстрый старт

```bash
cd affiliate-fanout

# 1. Проверить, что подключено (без постинга)
python3 -m affiliate_fanout --env .env --verify --json

# 2. Dry-run: план публикации
python3 -m affiliate_fanout --env .env \
  --brand-url https://www.aviasales.com/ --trs 597672 \
  --text "Cheap flights: {url}" \
  --platforms telegram,x,reddit,pinterest,bluesky,tumblr,telegraph --json

# 3. Реальная публикация
python3 -m affiliate_fanout --env .env \
  --brand-url https://www.aviasales.com/ --trs 597672 \
  --text "Cheap flights: {url}" \
  --platforms telegram,x,reddit,pinterest,bluesky,tumblr,telegraph \
  --tracker --execute
```

Платформа без кредов пропускается с ошибкой в отчёте, остальные работают.

---

## Переменные окружения

```dotenv
# --- Telegram (опционально через релей) ---
TELEGRAM_BOT_TOKEN=...
TELEGRAM_API_BASE=                       # опционально, если api.telegram.org
TELEGRAM_CHAT_ID_ALPHA=-100...           # любые каналы, TELEGRAM_CHAT_ID_*

# --- X (Twitter): OAuth 1.0a user context ---
X_API_KEY=... X_API_SECRET=...
X_ACCESS_TOKEN=... X_ACCESS_SECRET=...

# --- Reddit: OAuth2 script app ---
REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
REDDIT_USERNAME=... REDDIT_PASSWORD=... REDDIT_SUBREDDIT=...

# --- Pinterest (approved app + image) ---
PINTEREST_ACCESS_TOKEN=... PINTEREST_BOARD_ID=...
PINTEREST_IMAGE_URL=https://.../pin.jpg

# --- Meta: Facebook Page / Instagram / Threads ---
FACEBOOK_PAGE_ID=... FACEBOOK_PAGE_TOKEN=...
INSTAGRAM_USER_ID=... INSTAGRAM_ACCESS_TOKEN=... INSTAGRAM_IMAGE_URL=...
THREADS_USER_ID=... THREADS_ACCESS_TOKEN=...

# --- LinkedIn ---
LINKEDIN_ACCESS_TOKEN=... LINKEDIN_AUTHOR_URN=urn:li:person:...

# --- Medium (legacy) / Blogger / WordPress ---
MEDIUM_TOKEN=... MEDIUM_AUTHOR_ID=...
BLOGGER_CLIENT_ID=... BLOGGER_CLIENT_SECRET=... BLOGGER_REFRESH_TOKEN=... BLOGGER_BLOG_ID=...
WP_BASE_URL=https://blog.example.com WP_USERNAME=... WP_APP_PASSWORD=...
# или WordPress.com:
WPCOM_ACCESS_TOKEN=... WPCOM_SITE=example.wordpress.com

# --- Tumblr (OAuth 1.0a) ---
TUMBLR_CONSUMER_KEY=... TUMBLR_CONSUMER_SECRET=...
TUMBLR_OAUTH_TOKEN=... TUMBLR_OAUTH_TOKEN_SECRET=... TUMBLR_BLOG=my-blog

# --- Bluesky / Mastodon-совместимые ---
BLUESKY_HANDLE=... BLUESKY_APP_PASSWORD=...
MASTODON_BASE_URL=... MASTODON_TOKEN=...
AKKOMA_BASE_URL=... AKKOMA_TOKEN=...
PIXELFED_BASE_URL=... PIXELFED_TOKEN=...

# --- dev.to / Discord / Slack / Raindrop / Telegraph ---
DEVTO_API_KEY=...
DISCORD_WEBHOOK_URL=... SLACK_WEBHOOK_URL=...
RAINDROP_TOKEN=... RAINDROP_COLLECTION_ID=...
TELEGRAPH_TOKEN=                        # пусто = анонимный аккаунт

# --- Travelpayouts ---
TRAVELPAYOUTS_TOKEN=... TRAVELPAYOUTS_MARKER=... TRAVELPAYOUTS_TRS=...

# --- click-tracker ---
LINK_TRACKER_BASE=... LINK_TRACKER_ADMIN_TOKEN=...
```

---

## CLI

| Флаг | Назначение |
|---|---|
| `--env PATH` | загрузить `.env` (секреты не печатаются) |
| `--verify` | проверить подключения всех платформ |
| `--platforms all\|a,b,c` | `telegram,vk,tumblr,bluesky,mastodon,akkoma,pixelfed,devto,telegraph,discord,slack,raindrop,x,reddit,pinterest,facebook,instagram,threads,linkedin,medium,blogger,wordpress` |
| `--brand-url URL` | URL бренда → партнёрская ссылка Travelpayouts |
| `--url URL` | готовая ссылка (без конвертации) |
| `--trs ID` | ID проекта Travelpayouts |
| `--subid-prefix P` | префикс `sub_id`: `P_<platform>` (по умолчанию `fanout`) |
| `--text T` | шаблон поста, `{url}` подставляется |
| `--title T` | заголовок (Tumblr, Medium, Blogger, WordPress, Pinterest, Reddit) |
| `--disclosure S` | пометка рекламы (по умолчанию `Ad · affiliate link`) |
| `--tracker` | обернуть ссылки в свой `/r/<code>` |
| `--telegram-chat/-env/-all` | цели Telegram |
| `--resolve` | в dry-run создать партнёрские ссылки |
| `--execute` | реально публиковать |
| `--json` | отчёт в JSON |

Лимиты символов учитываются автоматически (`x 280`, `bluesky 300`,
`pinterest 500`, `threads 500`, `instagram 2200`, `telegram 4096`,
`linkedin 3000` и т.д.); ссылка и раскрытие всегда сохраняются.

---

## Бесплатные write-API: что где нужно (10.11.2026)

| Платформа | API | Бесплатный лимит | Что нужно для старта |
|---|---|---|---|
| Telegram | Bot API `sendMessage` | без квот, ~30 msg/сек | бот + админ в канале |
| X | `POST /2/tweets` (OAuth1) | 500 постов/мес | dev-аккаунт + app с Write |
| Reddit | `POST /api/submit` (OAuth2) | 100 QPM, **non-commercial** | script app; правила сабреддита |
| Pinterest | `POST /v5/pins` | Trial: 1000 req/день (пины приватны); Standard после ревью | business-аккаунт + видео-ревью OAuth |
| Facebook Page | `POST /{page-id}/feed` | бесплатно | Meta app + `pages_manage_posts` |
| Instagram | `/media` → `/media_publish` | бесплатно | Professional account + review |
| Threads | `/threads` → `/threads_publish` | бесплатно | Meta app + `threads_content_publish` |
| LinkedIn | `POST /rest/posts` | бесплатно | app + `w_member_social` |
| Medium | `POST /v1/users/{id}/posts` | ❌ новые токены не выдают | старый integration token |
| Blogger | `POST /blogger/v3/.../posts` | квота Google | OAuth2 refresh token |
| WordPress | REST `/wp-json/wp/v2/posts` / WP.com API | без лимитов (self-hosted) | Application Password / OAuth2 |
| Tumblr | `POST /v2/blog/{blog}/posts` | 300 req/мин | OAuth1-приложение |
| Bluesky | `createRecord` | 35 000 записей/день | app password |
| Mastodon/Akkoma/Pixelfed | `POST /api/v1/statuses` | лимит инстанса | токен приложения |
| dev.to | `POST /api/articles` | бесплатно | API key |
| Discord / Slack | webhooks | ~30 msg/мин / 1 msg/сек | webhook URL |
| Telegraph | `createPage` | бесплатно | без ключей |
| Raindrop | `POST /rest/v1/raindrop` | 120 req/мин | токен + коллекция |

**Закрыто/платно:** Hashnode (API платный с 13.05.2026), Medium (legacy),
Pinterest без ревью — пины невидимы, Reddit — commercial запрещён без
контракта, X — 500 постов/мес.

---

## GitHub: open-source стек для партнёрского стека (ноябрь 2026)

| Проект | ★ | Лицензия | Зачем |
|---|---|---|---|
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | 41 224 | AGPL-3.0 | self-hosted хаб публикаций в 30+ каналов, REST API/webhooks |
| [dubinc/dub.link](https://github.com/dubinc/dub.link) | 25 149 | AGPL-3.0 (open core) | короткие ссылки + клики + конверсии |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 209 960 | Sustainable Use | «клей»: cron/webhooks → пост → лог клика |
| [shlinkio/shlink](https://github.com/shlinkio/shlink) | 5 417 | MIT | smart-links на своём домене |
| [YOURLS/YOURLS](https://github.com/YOURLS/YOURLS) | 12 302 | MIT | простой shortener |
| [trypostit/trypost](https://github.com/trypostit/trypost) | 839 | AGPL-3.0 | API-first scheduler + MCP |
| [inovector/mixpost](https://github.com/inovector/mixpost) | 3 922 | MIT (Lite) | лёгкий планировщик (API/Pinterest — в Pro) |
| [LinkStackOrg/LinkStack](https://github.com/LinkStackOrg/LinkStack) | 3 946 | AGPL-3.0 | link-in-bio лендинг |
| [Zie619/n8n-workflows](https://github.com/Zie619/n8n-workflows) | 57 210 | MIT | 4 343 готовых workflow |
| [python-telegram-bot/python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | 29 568 | GPL-3.0 | полный контроль над Telegram-ботами |
| [praw-dev/praw](https://github.com/praw-dev/praw) | 4 295 | BSD-2-Clause | Reddit (по правилам сабреддитов) |

**Минимальный стек:** Postiz + Shlink + n8n в Docker. n8n — Sustainable Use
(не OSI), Mixpost API только в Pro, AGPL-проекты требуют открывать изменения
при сетевом использовании. Анти-паттерны: Selenium-боты для Pinterest,
«клоакинг»-репозитории, клон `postiz-cheap`.

---

## Как это устроено

```
affiliate_fanout/
├── env.py        # .env + os.environ, ConfigError
├── http.py       # stdlib HTTP, браузерный User-Agent
├── links.py      # Travelpayouts Links API + свой click-tracker
├── adapters.py   # 22 адаптера (Telegram, X, Reddit, Pinterest, Meta, LinkedIn,
│                 #   Medium, Blogger, WordPress, Tumblr, Bluesky, fediverse,
│                 #   dev.to, Discord/Slack, Telegraph, Raindrop, VK)
└── cli.py        # verify / dry-run / execute, лимиты, шаблоны
```

## Тесты

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v   # 21 тест, без сети
```

Мок-сервер эмулирует все API: OAuth1-подписи (Tumblr/X), OAuth2 (Reddit,
Blogger), link-facets Bluesky, Graph API Meta (2-шаговый publish), партнёрские
ссылки Travelpayouts, tracker, dry-run (ни одного POST), изоляция ошибок.

## Комплаенс

- Раскрытие рекламы: `--disclosure` (FTC/EU) — обязательно.
- Один канал = один `sub_id` — атрибуция источника.
- Travelpayouts: без брендов в объявлениях, без push/adult/мотивированного
  трафика, лимиты Links API (10 ссылок/запрос, 100 запросов/мин).
- Reddit: только non-commercial + правила сабреддитов; Pinterest/Meta — app
  review; X — free tier 500 постов/мес.

## Лицензия

MIT — см. [LICENSE](LICENSE).
