# affiliate-fanout

[![tests](https://github.com/valdislavn-spec/affiliate-fanout/actions/workflows/tests.yml/badge.svg)](https://github.com/valdislavn-spec/affiliate-fanout/actions/workflows/tests.yml) [![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://github.com/valdislavn-spec/affiliate-fanout) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Публикация партнёрских ссылок во все бесплатные соцсети через API** — один
пост, везде свой `sub_id`, свой click-tracker и обязательное раскрытие
«реклама / партнёрская ссылка».

- **0 зависимостей** — только Python standard library (3.9+).
- **12 бесплатных каналов**: Telegram (Bot API/релей), VK, Tumblr, Bluesky,
  Akkoma / Pixelfed / Mastodon (Mastodon API), dev.to, Discord/Slack webhooks,
  Telegraph, Raindrop.io.
- **Travelpayouts**: на каждый канал создаётся своя партнёрская ссылка с
  `sub_id=<prefix>_<platform>` через Partner Links API.
- **Свой click-tracker**: каждая ссылка оборачивается в `/r/<code>` для
  статистики кликов по платформам.
- **Безопасно по умолчанию**: dry-run, постинг только с `--execute`,
  раскрытие добавляется автоматически.
- **19 офлайн-тестов** на stdlib `unittest` с мок-сервером всех API.

> Независимый open-source проект. Партнёрские ссылки нужно сопровождать
> раскрытием (FTC/EU) — флаг `--disclosure` включён по умолчанию.

---

## Проверенные подключения (09.11.2026)

| Канал | Статус | Аккаунт |
|---|---|---|
| Telegram Bot API (релей) | ✅ | настроен, 4 канала |
| Tumblr API v2 | ✅ | настроен (блог) |
| Bluesky AT Protocol | ✅ | настроен |
| Akkoma | ✅ | настроен (Akkoma) |
| Pixelfed | ✅ | настроен (Pixelfed) |
| Telegraph | ✅ | без авторизации |
| Свой link-tracker | ✅ | 23 ссылки, коды `fanout-*` |
| Travelpayouts Links API | ✅ | токен + маркер (нужен `TRAVELPAYOUTS_TRS`) |
| Mastodon | ⚠️ | аккаунт отключён на инстансе (нужен другой инстанс/аккаунт) |
| VK | ⚠️ | нужен `VK_ACCESS_TOKEN` (сейчас пуст) — код готов (`wall.post`) |
| dev.to | ⚠️ | нужен `DEVTO_API_KEY` (Settings → Extensions → DEV Community API Keys) |
| Raindrop.io | ⚠️ | нужен `RAINDROP_TOKEN` + коллекция (публичный link-hub) |
| Discord / Slack | ⚠️ | нужны webhook URL |
| X / Facebook / Instagram / Threads / LinkedIn / Medium | ⚠️ | нужны токены/ревью приложения |
| Reddit | ❌ | API закрыт для новых ключей (31.10.2026) |
| Pinterest | ⚠️ | приложение на ревью; официальный API после аппрува |

Проверить на своей машине: `python -m affiliate_fanout --env .env --verify`

Готовые ссылки под каждую платформу (Travelpayouts `sub_id` + свой tracker)
генерируются в `local/links-ready.json` (каталог в `.gitignore`) — их можно
вставлять в посты/био/лендинги без запуска публикации.

---

## Быстрый старт

```bash
cd affiliate-fanout

# 1. Проверить, что уже подключено (без постинга)
python3 -m affiliate_fanout --env ../content-factory/.env --verify --json

# 2. Dry-run: посмотреть план, ничего не публикуя
python3 -m affiliate_fanout \
  --env ../content-factory/.env \
  --brand-url https://www.aviasales.com/ --trs 597672 \
  --text "Дешёвые билеты: {url}" \
  --platforms telegram,tumblr,bluesky,akkoma,pixelfed,telegraph \
  --telegram-all --json

# 3. Реальная публикация (партнёрские ссылки + tracker + все каналы)
python3 -m affiliate_fanout \
  --env ../content-factory/.env \
  --brand-url https://www.aviasales.com/ --trs 597672 \
  --text "Дешёвые билеты: {url}" \
  --platforms telegram,tumblr,bluesky,akkoma,pixelfed,telegraph \
  --telegram-all --tracker --execute
```

`--telegram-all` берёт все непустые `TELEGRAM_CHAT_ID_*` из env.
Точечно: `--telegram-chat -1001234567890` или
`--telegram-env TECH_AI_ES,CRYPTO_ES`.

---

## Что нужно в `.env`

```dotenv
# --- Telegram (можно через релей, если api.telegram.org блокируется) ---
TELEGRAM_BOT_TOKEN=...
TELEGRAM_API_BASE=https://telegram-proxy.example.workers.dev   # опционально
TELEGRAM_CHAT_ID_ALPHA=-100...                                  # любые каналы

# --- Tumblr (OAuth 1.0a) ---
TUMBLR_CONSUMER_KEY=... TUMBLR_CONSUMER_SECRET=...
TUMBLR_OAUTH_TOKEN=...  TUMBLR_OAUTH_TOKEN_SECRET=...
TUMBLR_BLOG=my-blog

# --- Bluesky ---
BLUESKY_HANDLE=user.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx          # Settings → App Passwords

# --- Mastodon-совместимые сети (Akkoma, Pixelfed, Mastodon) ---
AKKOMA_BASE_URL=https://akkoma.example   AKKOMA_TOKEN=...
PIXELFED_BASE_URL=https://pixelfed.example PIXELFED_TOKEN=...
MASTODON_BASE_URL=https://mastodon.social MASTODON_TOKEN=...

# --- Discord webhook (опционально) ---
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# --- Telegraph (опционально; без токена создаётся анонимный аккаунт) ---
TELEGRAPH_TOKEN=

# --- Travelpayouts (партнёрские ссылки с sub_id) ---
TRAVELPAYOUTS_TOKEN=...      # X-Access-Token
TRAVELPAYOUTS_MARKER=...     # публичный маркер
TRAVELPAYOUTS_TRS=...        # ID проекта (можно --trs)

# --- Свой click-tracker (опционально) ---
LINK_TRACKER_BASE=https://links-tracker.example.workers.dev
LINK_TRACKER_ADMIN_TOKEN=...
```

Платформа без кредов просто пропускается с ошибкой в отчёте — остальные
каналы продолжают работать.

---

## CLI

| Флаг | Назначение |
|---|---|
| `--env PATH` | загрузить `.env` (секреты не печатаются) |
| `--verify` | проверить подключения (Telegram, Tumblr, Bluesky, fediverse, Telegraph, tracker) |
| `--platforms all\|a,b,c` | каналы (`telegram,vk,tumblr,bluesky,mastodon,akkoma,pixelfed,devto,telegraph,discord,slack,raindrop`) |
| `--brand-url URL` | URL бренда → партнёрская ссылка Travelpayouts |
| `--url URL` | готовая ссылка (без конвертации) |
| `--trs ID` | ID проекта Travelpayouts, если нет в env |
| `--subid-prefix P` | префикс `sub_id`: `P_<platform>` (по умолчанию `fanout`) |
| `--text T` | шаблон поста, `{url}` подставляется |
| `--title T` | заголовок для Tumblr/Telegraph |
| `--disclosure S` | пометка рекламы (по умолчанию `Ad · affiliate link`) |
| `--tracker` | обернуть ссылки в свой `/r/<code>` |
| `--telegram-chat/-env/-all` | цели Telegram |
| `--resolve` | в dry-run создать партнёрские ссылки |
| `--execute` | реально публиковать |
| `--json` | отчёт в JSON |

Коды выхода: `0` — успех/частично, `1` — были ошибки платформ,
`2` — ошибка конфигурации.

---

## Как это устроено

```
affiliate_fanout/
├── env.py        # .env + os.environ, ConfigError
├── http.py       # stdlib HTTP, браузерный User-Agent
├── links.py      # Travelpayouts Links API + свой click-tracker
├── adapters.py   # Telegram, VK, Tumblr (OAuth1), Bluesky (AT), fediverse,
│                 dev.to, Discord/Slack, Telegraph, Raindrop
└── cli.py        # verify / dry-run / execute, шаблоны и лимиты платформ
```

Лимиты символов учитываются автоматически (`telegram 4096`, `bluesky 300`,
`discord 2000`, `pixelfed 2200` и т.д.). Ссылка и раскрытие всегда остаются в
тексте даже после обрезки.

---

## Тесты

```bash
PYTHONPATH=. python3 -m unittest discover -s tests -v   # 19 тестов, без сети
```

Мок-сервер эмулирует все API: проверяются OAuth-подпись Tumblr, link-facets
Bluesky, VK `wall.post`, dev.to, Raindrop, Slack, партнёрские ссылки
Travelpayouts, обёртка tracker, dry-run (ни одного POST), изоляция ошибок
одной платформы от остальных.

---

## GitHub: что ещё стоит посмотреть (open-source стек, ноябрь 2026)

| Проект | ★ | Лицензия | Зачем |
|---|---|---|---|
| [gitroomhq/postiz-app](https://github.com/gitroomhq/postiz-app) | 41 224 | AGPL-3.0 | self-hosted планировщик в 30+ каналов, REST API/webhooks — «хаб публикаций» |
| [dubinc/dub.link](https://github.com/dubinc/dub.link) | 25 149 | AGPL-3.0 (open core) | короткие ссылки + клики + конверсии (лучший OSS для атрибуции) |
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 209 960 | Sustainable Use | «клей»: cron/webhooks → пост → лог клика |
| [shlinkio/shlink](https://github.com/shlinkio/shlink) | 5 417 | MIT | shortener с dynamic redirects и статистикой |
| [YOURLS/YOURLS](https://github.com/YOURLS/YOURLS) | 12 302 | MIT | простой shortener на своём домене |
| [thedevs-network/kutt](https://github.com/thedevs-network/kutt) | 11 197 | MIT | shortener с админкой |
| [trypostit/trypost](https://github.com/trypostit/trypost) | 839 | AGPL-3.0 | API-first scheduler + MCP |
| [inovector/mixpost](https://github.com/inovector/mixpost) | 3 922 | MIT (Lite) | лёгкий планировщик; API/Pinterest — в Pro |
| [LinkStackOrg/LinkStack](https://github.com/LinkStackOrg/LinkStack) | 3 946 | AGPL-3.0 | link-in-bio лендинг |
| [Zie619/n8n-workflows](https://github.com/Zie619/n8n-workflows) | 57 210 | MIT | 4 343 готовых workflow (RSS→соцсети, UTM) |
| [python-telegram-bot/python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) | 29 568 | GPL-3.0 | полный контроль над Telegram-ботами |
| [python273/vk_api](https://github.com/python273/vk_api) | 1 365 | Apache-2.0 | VK `wall.post`, LongPoll |
| [praw-dev/praw](https://github.com/praw-dev/praw) | 4 295 | BSD-2-Clause | Reddit API (только с учётом правил сабреддитов) |

**Не брать без аудита:** `SamurAIGPT/postiz-cheap` (не связан с Postiz),
`yawaweb/link-cloaker` (мёртв, 2021), Pinterest-боты на Selenium (против ToS).

---

## Комплаенс

- Партнёрские ссылки — только с пометкой рекламы (`--disclosure`).
- Не спамить в чужие каналы/сабреддиты; каждый канал — свой `sub_id` для
  аналитики источника.
- Соблюдать правила Travelpayouts (запрещены бренды в объявлениях, push,
  adult, мотивированный трафик) и лимиты API (Links API: 10 ссылок/запрос,
  100 запросов/мин).
- GitHub AUP: реклама — только в своих README/проектах, без спама в чужих
  issues/репозиториях.

## Лицензия

MIT — см. [LICENSE](LICENSE).
