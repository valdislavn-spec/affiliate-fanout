# Pinterest — Standard access (видео-ревью)

Trial-доступ даёт пины, но они **приватные** (не видны людям). Чтобы публиковать
реально, нужен **Standard access**: подача с видео-демо OAuth-флоу.

## Шаги

1. https://developers.pinterest.com → **My apps → Create app**.
2. Заполнить:
   - App name: `Travel Deals Studio`;
   - Description: “Publishes our own travel deal posts (with affiliate
     disclosure) to our boards.”;
   - Website: `https://valdislavn-spec.github.io/travel-finds/`;
   - Privacy: `.../privacy.html`; Terms: `.../terms.html`.
3. **Configure → Redirect URIs**:
   `https://valdislavn-spec.github.io/travel-finds/oauth-callback.html`
4. Scopes: `pins:read`, `pins:write`, `boards:read`.
5. **Request Standard access** → приложить:
   - видео 60–90 сек по [screencast-script.md](screencast-script.md) (показать
     OAuth-флоу + создание пина с картинкой и ссылкой);
   - короткий текст use-case из [app-metadata.md](app-metadata.md).
6. После одобрения (3–10 дней):
   ```bash
   python3 tools/oauth_tokens.py --provider pinterest \
     --client-id ... --client-secret ... --url
   # затем --exchange "<code>"
   ```
   `.env`: `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_ID`,
   `PINTEREST_IMAGE_URL` (публичный HTTPS, напр. og-cover с сайта).
7. Проверка: `--verify` → `pinterest OK`.

## Нюансы

- Пин обязан иметь `media_source` (image_url); текст без картинки не публикуется.
- Trial: 1000 запросов/день, org_write 300/день, пины приватны.
- Standard: 100 req/сек; ссылка должна вести на релевантный лендинг (не
  клоакинг), иначе отклонят/забанят.
- Pinterest требует раскрытие партнёрства, если пин ведёт на affiliate-ссылку.
