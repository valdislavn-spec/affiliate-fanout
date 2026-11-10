# Meta (Facebook / Instagram / Threads) — ревью

Самый долгий путь: приложение Business + Business Verification + App Review на
каждое разрешение. Ревью требует screencast (см. скрипт) и работающую
OAuth-страницу.

## 1. Приложение

1. https://developers.facebook.com/apps → **Create app** → тип **Business**.
2. App name: `Travel Deals Studio`.
3. **App settings → Basic**:
   - App Domains: `valdislavn-spec.github.io`
   - Privacy Policy URL: `https://valdislavn-spec.github.io/travel-finds/privacy.html`
   - Terms of Service URL: `https://valdislavn-spec.github.io/travel-finds/terms.html`
   - Category: Travel / Content management
   - Contact email: ваш.
4. **Add products**:
   - Facebook Login for Business → Settings: Valid OAuth Redirect URIs:
     `https://valdislavn-spec.github.io/travel-finds/oauth-callback.html`;
     Client OAuth Login = ON; Web OAuth Login = ON.
   - Instagram Graph API (или Instagram API with Facebook Login).
   - Threads API.
5. Верификация домена: **Business settings → Brand safety → Domains** →
   добавить `valdislavn-spec.github.io` → мета-тег/HTML-файл на сайт (файл
   можно положить в репозиторий travel-finds).

## 2. Business Verification

**Business settings → Security Center → Business verification** — понадобятся
реквизиты (юрлицо/ИП/самозанятость) и подтверждение домена/телефона. Без этого
advanced-доступ к `pages_manage_posts`/`instagram_content_publish` не выдадут.

## 3. App Review

Для каждого разрешения: **App Review → Permissions and features → Request**:

| Permission | Зачем в нашем кейсе |
|---|---|
| `pages_show_list` | список наших страниц |
| `pages_read_engagement` | чтение метаданных страницы |
| `pages_manage_posts` | публикация постов на нашей странице |
| `instagram_basic` | профиль нашего IG-аккаунта |
| `instagram_content_publish` | публикация в наш IG |
| `threads_basic` | профиль нашего Threads |
| `threads_content_publish` | публикация в наш Threads |

К каждой заявке: описание use-case из [app-metadata.md](app-metadata.md),
screencast, ссылка на privacy policy.

## 4. Токены после одобрения

```bash
# OAuth → code → long-lived user token → page token
python3 tools/oauth_tokens.py --provider meta \
  --client-id ... --client-secret ... --url
python3 tools/oauth_tokens.py --provider meta \
  --client-id ... --client-secret ... --exchange "<code>"
```

Скрипт напечатает:
`FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`, `INSTAGRAM_USER_ID`,
`INSTAGRAM_ACCESS_TOKEN`, `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`
(если аккаунты привязаны к странице).

Проверка: `--verify` → `facebook OK`, `instagram OK`, `threads OK`.

## Нюансы

- Токены страниц долгоживущие (60 дней); продлевать через long-lived exchange.
- Instagram/Threads публикуют только **media** (image_url) для IG; Threads
  поддерживает текст.
- Meta запрещает автоматический постинг в личные профили/группы — только свои
  страницы/профессиональные аккаунты.
- Ревью может занять 1–3 недели; отклоняют чаще всего за неработающий
  redirect URI, отсутствие privacy policy или screencast без OAuth-флоу.
