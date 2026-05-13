# Отчёт по проекту The Bazaar Live Board

Дата: 2026-05-04

## Сервер

- VPS: `31.57.93.123`
- Проект на сервере: `/opt/thebazaar-twitch-extension`
- Сайт: `https://thebazaar-twitch.online`
- API: `https://api.thebazaar-twitch.online`
- Схема работы: `nginx -> Docker/FastAPI EBS -> Twitch`
- Nginx настроен, SSL работает.
- Проверенные маршруты:
  - `/new -> 200`
  - `/register -> 200`
  - `/health -> 200`

## Сайт

- Главная витрина: `https://thebazaar-twitch.online/new?lang=ru`
- Регистрация: `https://thebazaar-twitch.online/register?lang=ru`

На главной сделано:

- современный лендинг;
- галерея-заготовка под видео и скриншоты;
- кнопка `Зарегистрироваться`;
- подвал с почтой `adeptas3@gmail.com`;
- Discord пока заглушка `Discord группа: скоро`;
- ссылка на скачивание приложения добавлена, но скрыта до релиза.

## Регистрация

- Убрали поле `Twitch Channel ID`.
- Пользователь вводит только:
  - `Twitch Nick`;
  - email;
  - язык.
- Сервер сам резолвит Twitch Nick в числовой Twitch ID.
- Сервер выдаёт `Companion Token`.
- Токен хранится на сервере только как hash.
- Письмо отправляется через Yandex Cloud Postbox.

## Desktop Companion

- `.exe` собран локально:

```text
C:\Users\users\Desktop\Новая папка (2)\plaginTwich\dist\TheBazaarLiveBoardCompanion\TheBazaarLiveBoardCompanion.exe
```

- Версия в коде: `0.8.1-twitch-nick`
- Поле `Channel ID` заменено на `Twitch Nick`.
- Авторизация работает по `Twitch Nick + Companion Token`.
- Есть:
  - RU/EN язык;
  - Verify;
  - Start/Stop/Test;
  - калибровка боксов;
  - визуальный fallback для неизвестных карт.

## Проверки

Локальные тесты проходили:

```text
31 passed
```

Серверные маршруты проверены:

```text
/new -> 200
/register -> 200
/health -> 200
```

## Что делать дальше

1. Дать реальную ссылку на Discord группу и вставить её в подвал.
2. Подготовить реальные видео и скриншоты для галереи.
3. Решить, когда выкладывать `.exe` на сервер и включать кнопку скачивания.
4. Протестировать полный путь:
   - регистрация;
   - письмо;
   - ввод nick/token в приложение;
   - Verify;
   - Start;
   - данные в Twitch Extension.
