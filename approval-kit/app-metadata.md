# App metadata (копировать в формы)

## Общие поля

- Website: `https://valdislavn-spec.github.io/travel-finds/`
- Privacy policy: `https://valdislavn-spec.github.io/travel-finds/privacy.html`
- Terms: `https://valdislavn-spec.github.io/travel-finds/terms.html`
- OAuth redirect URI: `https://valdislavn-spec.github.io/travel-finds/oauth-callback.html`
- Support/contact: `https://github.com/valdislavn-spec/affiliate-fanout/issues`
- App category: Travel / Content publishing / Social media management
- Platform: Web (server-side + local CLI)

## Название и описание

- App name: **Travel Deals Studio**
- Short description (EN): “Publishes travel deal posts with disclosed affiliate links
  to our own social accounts.”
- Full description: “Travel Deals Studio is an internal publishing tool for our
  travel content sites (EN/ES). It composes short travel-deal posts, attaches
  affiliate links with an explicit disclosure, and publishes them to our own
  accounts. No third-party content is collected; no user accounts are offered.”

## Use case (для ревью Meta/Pinterest/LinkedIn)

“We operate travel content sites and social channels (US + Latin America, EN/ES).
Our editorial team uses this tool to publish our own travel deals. The app only
posts to accounts owned by us; it does not read private messages, does not
collect user data, and each post contains an affiliate disclosure.”

## Переменные `.env` после одобрения

```dotenv
# X (OAuth 1.0a user context; ключи из X Developer Portal → Keys and tokens)
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=

# Meta: Facebook Page
FACEBOOK_PAGE_ID=
FACEBOOK_PAGE_TOKEN=

# Meta: Instagram
INSTAGRAM_USER_ID=
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_IMAGE_URL=https://valdislavn-spec.github.io/travel-finds/assets/og-cover.png

# Meta: Threads
THREADS_USER_ID=
THREADS_ACCESS_TOKEN=

# Pinterest
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_ID=
PINTEREST_IMAGE_URL=https://valdislavn-spec.github.io/travel-finds/assets/og-cover.png

# LinkedIn
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_AUTHOR_URN=urn:li:person:<your-id>
```

## Scopes / permissions по платформам

| Платформа | Permissions |
|---|---|
| X | OAuth 1.0a user context, Read and Write |
| Meta Facebook Page | `pages_show_list`, `pages_read_engagement`, `pages_manage_posts` |
| Meta Instagram | `instagram_basic`, `instagram_content_publish`, `pages_show_list` |
| Meta Threads | `threads_basic`, `threads_content_publish` |
| Pinterest | `pins:read`, `pins:write`, `boards:read` |
| LinkedIn | `openid profile w_member_social` |
