# Screencast для ревью (Pinterest / Meta), 60–90 секунд

Записать экран (QuickTime → Screen Recording, 1080p, английская озвучка или
субтитры). **Не показывать токены, пароли, email.**

## Сценарий

1. **0:00–0:10 — Контекст.** Открыть https://valdislavn-spec.github.io/travel-finds/
   (EN) и https://valdislavn-spec.github.io/travel-finds/es.html (ES):
   «These are our travel content sites for US and Latin America audiences.»
2. **0:10–0:25 — Публикация.** Открыть терминал и показать dry-run:
   ```bash
   python3 -m affiliate_fanout --env .env --market us \
     --brand-url https://www.trip.com/ --trs <id> \
     --platforms pinterest --json
   ```
   Показать план поста: текст, ссылка, пометка `Ad · affiliate link`.
3. **0:25–0:50 — OAuth.** Открыть ссылку авторизации из
   `tools/oauth_tokens.py --provider pinterest --url`; показать экран
   согласия Pinterest; разрешить доступ; callback-страница показывает `code`;
   скопировать код → вставить в `--exchange`; показать `PINTEREST_ACCESS_TOKEN`
   (замазать значение).
4. **0:50–1:10 — Проверка и пост.** Запустить с `--execute` на тестовый борд;
   открыть созданный пин (видна картинка, ссылка, описание). Показать, что
   публикация успешна.
5. **1:10–1:25 — Дисклеймер.** Показать в посте `Ad · affiliate link` и
   страницу privacy policy.

## Чек-лист перед загрузкой

- [ ] Видно домен приложения/сайта.
- [ ] Видно экран OAuth-согласия и callback.
- [ ] Видно успешную публикацию в аккаунт (не в редактор).
- [ ] Никаких токенов/секретов на экране.
- [ ] Видео ≤ 2 минут, MP4, 1080p, ссылка доступна без авторизации (YouTube
      unlisted / Google Drive «anyone with link»).
