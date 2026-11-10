# X (Twitter) — free tier, без ревью

X не требует «одобрения» как Meta/Pinterest: приложение self-serve, но нужен
developer-аккаунт с подтверждённым телефоном. Free tier: **500 постов/мес**.

## Шаги

1. https://developer.x.com → **Sign up** (тот же аккаунт, что публикует).
2. **Developer Portal → Projects & Apps → Create App** (Free tier).
3. App name: `Travel Deals Studio`; use case: «publishing our own travel content».
4. **Keys and tokens**:
   - API Key / API Secret (consumer keys);
   - Access Token / Access Token Secret — сгенерировать с правами **Read and Write**
     (Settings → User authentication settings → OAuth 1.0a, App permissions:
     Read and Write).
5. Записать в `.env`: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`.
6. Проверка: `python3 -m affiliate_fanout --env .env --verify` → `x OK @handle`.

## Нюансы

- Free tier даёт 500 постов/мес (~16/день) и ~100 чтений/мес; для нашего
  пайплайна этого хватает.
- Нельзя использовать несколько аккаунтов/приложений для обхода лимита.
- Внешние ссылки снижают охват — давайте нативный текст + ссылку.
- Альтернатива: OAuth2 PKCE (`tools/oauth_tokens.py --provider x`), если
  предпочитаете user-context OAuth2; тогда в `.env` нужны `X_CLIENT_ID`,
  `X_CLIENT_SECRET`, `X_REFRESH_TOKEN` (адаптер сейчас на OAuth1 — быстрее
  через Keys and tokens).
