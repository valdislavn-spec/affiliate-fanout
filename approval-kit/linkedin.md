# LinkedIn — self-serve (без ревью)

LinkedIn API для постинга от своего имени открывается self-serve, если
приложение привязано к странице компании.

## Шаги

1. https://www.linkedin.com/developers/apps → **Create app**.
   - App name: `Travel Deals Studio`
   - LinkedIn Page: ваша Company Page (создать, если нет)
   - App logo, legal terms/privacy URLs:
     `https://valdislavn-spec.github.io/travel-finds/privacy.html`
2. Вкладка **Auth**:
   - Redirect URL: `https://valdislavn-spec.github.io/travel-finds/oauth-callback.html`
   - Запросить продукты: **Share on LinkedIn** (`w_member_social`) и
     **Sign In with LinkedIn using OpenID Connect** (`openid profile email`).
3. Скопировать `Client ID` / `Client Secret`.
4. Получить токен:
   ```bash
   # 1) ссылка авторизации (откройте в браузере под нужным аккаунтом)
   python3 tools/oauth_tokens.py --provider linkedin \
     --client-id ... --client-secret ... --url
   # 2) после согласия браузер откроет callback-страницу — скопируйте code
   python3 tools/oauth_tokens.py --provider linkedin \
     --client-id ... --client-secret ... --exchange "<code>"
   ```
5. `.env`: `LINKEDIN_ACCESS_TOKEN=...`, `LINKEDIN_AUTHOR_URN=urn:li:person:<id>`
   (`<id>` — ваш LinkedIn person id; можно получить через `/v2/userinfo` → `sub`).
6. Проверка: `--verify` → `linkedin OK`.

## Нюансы

- Токен живёт ~60 дней; refresh token — 365 дней (запросить `refresh_token` в
  scopes, если появится).
- Постим только от своего имени (`w_member_social`), страницы компании — через
  отдельный product (`w_organization_social`, требует проверки).
- Комментарий к посту — до 3000 символов.
