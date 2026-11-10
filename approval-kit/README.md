# Approval kit — X, Meta, Pinterest, LinkedIn

Готовый пакет для подачи приложений на одобрение. Всё, что нужно от вас —
залогиниться в кабинетах разработчиков и вставить готовые тексты/URL.

## Что уже опубликовано (нужно для ревью)

| Документ | URL |
|---|---|
| Сайт (website) | https://valdislavn-spec.github.io/travel-finds/ |
| Privacy Policy | https://valdislavn-spec.github.io/travel-finds/privacy.html |
| Terms of Use | https://valdislavn-spec.github.io/travel-finds/terms.html |
| OAuth callback (redirect URI) | https://valdislavn-spec.github.io/travel-finds/oauth-callback.html |

Контакты для форм: `https://github.com/valdislavn-spec/affiliate-fanout/issues`.

## Статус и порядок подачи

| Платформа | Что нужно | Ревью? | Реалистичный срок | Файл |
|---|---|---|---|---|
| **X (Twitter)** | Developer app + Write permission (free tier 500/мес) | Нет, self-serve (нужен телефон) | часы | [x.md](x.md) |
| **LinkedIn** | App + «Share on LinkedIn» (`w_member_social`) + «Sign In with LinkedIn (OpenID)» | Нет (self-serve), иногда проверка страницы | 1–2 дня | [linkedin.md](linkedin.md) |
| **Pinterest** | App → Standard access + видео-демо OAuth | Да, видео-ревью | 3–10 дней | [pinterest.md](pinterest.md) |
| **Meta (FB/IG/Threads)** | App (Business) + permissions + Business Verification + screencast | Да | 1–3 недели | [meta.md](meta.md) |

Сначала X и LinkedIn (быстро), параллельно подавать Pinterest, Meta — последней
(самое долгое ревью). Email (Brevo) — по вашему решению пока не трогаем.

## Что подготовить один раз

- [ ] Meta Business Portfolio (для Meta-ревью).
- [ ] Страница Facebook (проект/бренд) и профессиональный Instagram-аккаунт — они же «платформы публикации».
- [ ] LinkedIn Company Page (для проверки приложения).
- [ ] Скринкаст 60–90 сек по [screencast-script.md](screencast-script.md) — записывается после того, как приложение создано.
- [ ] Приложение для домена `valdislavn-spec.github.io` (мета-тег проверки домена Meta).

## После одобрения

1. Выпустить токены: `python3 tools/oauth_tokens.py --provider meta ...` (см. [README tools](../tools/oauth_tokens.py)).
2. Заполнить `.env` (переменные — в [app-metadata.md](app-metadata.md)).
3. Проверить: `python3 -m affiliate_fanout --env .env --verify` → X/Meta/Pinterest/LinkedIn должны стать `OK`.
4. Запустить `--market us` / `--market latam` с `--execute`.
