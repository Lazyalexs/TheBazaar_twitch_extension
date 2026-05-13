from __future__ import annotations

from html import escape

from .database import SUPPORTED_LANGUAGES, normalize_language


CONTACT_EMAIL = "adeptas3@gmail.com"
DISCORD_URL = ""
STREAMER_APP_DOWNLOAD_URL = "/downloads/TheBazaarLiveBoardCompanion.exe"
SHOW_STREAMER_APP_DOWNLOAD = True


TEXT = {
    "ru": {
        "brand": "The Bazaar Live Board",
        "landing_title": "Живая доска The Bazaar прямо поверх Twitch-стрима",
        "landing_subtitle": (
            "Companion читает игру у стримера, отправляет состояние на сервер, "
            "а зрители видят интерактивные карточки и подсказки в расширении Twitch."
        ),
        "landing_eyebrow": "Twitch companion для стримеров",
        "register_cta": "Зарегистрироваться",
        "download_cta": "Скачать приложение",
        "gallery_video": "Видео демо",
        "gallery_screen_1": "Скриншот оверлея",
        "gallery_screen_2": "Скриншот приложения",
        "gallery_note": "Сюда добавим реальные видео и скриншоты перед релизом.",
        "feature_1_title": "Автоматическое распознавание",
        "feature_1_text": "Карточки берутся из логов игры, а неизвестные элементы проверяются визуально.",
        "feature_2_title": "Личный токен",
        "feature_2_text": "Каждый стример получает отдельный Companion Token, на сервере хранится только hash.",
        "feature_3_title": "Готово для Twitch",
        "feature_3_text": "После проверки приложение публикует доску в Twitch Extension без ручной настройки зрителей.",
        "how_title": "Как это работает",
        "how_1": "Стример регистрирует Twitch nick и получает Companion Token.",
        "how_2": "Desktop companion читает The Bazaar и отправляет live snapshot.",
        "how_3": "Twitch Extension показывает hover-зоны, карточки и подсказки зрителям.",
        "register_page_title": "The Bazaar Live Board - регистрация",
        "register_title": "Регистрация стримера",
        "register_subtitle": "Введи Twitch nick канала и получи личный Companion Token для приложения.",
        "form_title": "Данные канала",
        "channel_login": "Twitch Nick",
        "channel_hint": "Никнейм канала Twitch, например lazyalexs. Можно вставить ссылку на канал.",
        "email": "Email",
        "email_hint": "На эту почту отправим Twitch Nick и Companion Token.",
        "language": "Язык",
        "submit": "Получить токен",
        "result_title": "Данные для приложения",
        "result_note": "Сохрани токен сейчас. Позже его нельзя будет посмотреть, только выдать новый.",
        "copy": "Копировать",
        "channel_label": "Twitch Nick",
        "token_label": "Companion Token",
        "open_app": "Вставь эти значения в companion app и нажми Verify.",
        "email_sent": "Письмо отправлено на email.",
        "email_not_sent": "Почта не отправлена, но данные ниже уже рабочие.",
        "registering": "Регистрирую...",
        "copied": "Скопировано",
        "failed": "Не получилось зарегистрировать",
        "footer_product": "Companion для The Bazaar stream overlay.",
        "footer_contacts": "Контакты",
        "footer_email": "Почта",
        "footer_discord": "Discord группа",
        "footer_discord_soon": "Discord группа: скоро",
        "footer_links": "Ссылки",
        "footer_site": "Главная",
        "footer_register": "Регистрация",
        "footer_release": "Скачать приложение для стримеров",
        "lang_switch": "EN",
    },
    "en": {
        "brand": "The Bazaar Live Board",
        "landing_title": "A live The Bazaar board layered over your Twitch stream",
        "landing_subtitle": (
            "The companion reads the streamer's game, sends state to the server, "
            "and viewers get interactive cards and tooltips in the Twitch Extension."
        ),
        "landing_eyebrow": "Twitch companion for streamers",
        "register_cta": "Register",
        "download_cta": "Download app",
        "gallery_video": "Demo video",
        "gallery_screen_1": "Overlay screenshot",
        "gallery_screen_2": "App screenshot",
        "gallery_note": "Real videos and screenshots will be added here before release.",
        "feature_1_title": "Automatic recognition",
        "feature_1_text": "Cards come from game logs, while unknown items can be checked visually.",
        "feature_2_title": "Private token",
        "feature_2_text": "Every streamer gets a separate Companion Token; the server stores only its hash.",
        "feature_3_title": "Twitch ready",
        "feature_3_text": "After verification the app publishes the board to the Twitch Extension.",
        "how_title": "How it works",
        "how_1": "The streamer registers a Twitch nick and receives a Companion Token.",
        "how_2": "The desktop companion reads The Bazaar and sends a live snapshot.",
        "how_3": "The Twitch Extension renders hover zones, cards, and tooltips for viewers.",
        "register_page_title": "The Bazaar Live Board - registration",
        "register_title": "Streamer registration",
        "register_subtitle": "Enter your Twitch nick and receive a private Companion Token for the app.",
        "form_title": "Channel details",
        "channel_login": "Twitch Nick",
        "channel_hint": "Your Twitch channel nickname, for example lazyalexs. A channel link also works.",
        "email": "Email",
        "email_hint": "We will send the Twitch Nick and Companion Token to this email.",
        "language": "Language",
        "submit": "Get token",
        "result_title": "App credentials",
        "result_note": "Save this token now. It cannot be shown later, only regenerated.",
        "copy": "Copy",
        "channel_label": "Twitch Nick",
        "token_label": "Companion Token",
        "open_app": "Paste these values into the companion app and press Verify.",
        "email_sent": "Email sent.",
        "email_not_sent": "Email was not sent, but the credentials below already work.",
        "registering": "Registering...",
        "copied": "Copied",
        "failed": "Registration failed",
        "footer_product": "Companion for The Bazaar stream overlay.",
        "footer_contacts": "Contacts",
        "footer_email": "Email",
        "footer_discord": "Discord group",
        "footer_discord_soon": "Discord group: soon",
        "footer_links": "Links",
        "footer_site": "Home",
        "footer_register": "Registration",
        "footer_release": "Download streamer app",
        "lang_switch": "RU",
    },
}


def supported_language(language: str | None) -> str:
    clean = normalize_language(language)
    return clean if clean in SUPPORTED_LANGUAGES else "ru"


def _styles() -> str:
    return """
    :root {
      color-scheme: dark;
      --bg: #08090b;
      --surface: #111316;
      --surface-2: #17140f;
      --panel: rgba(19, 21, 24, .86);
      --line: rgba(255, 255, 255, .14);
      --text: #f7f2ea;
      --muted: #bdb3a7;
      --gold: #f4c34e;
      --cyan: #4cc7e8;
      --green: #67d48f;
      --coral: #ff7c66;
      --violet: #9b86ff;
      --shadow: 0 24px 70px rgba(0, 0, 0, .34);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 12% 10%, rgba(244, 195, 78, .14), transparent 24rem),
        radial-gradient(circle at 86% 12%, rgba(76, 199, 232, .14), transparent 24rem),
        linear-gradient(145deg, #08090b 0%, #101815 48%, #160f12 100%);
      color: var(--text);
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: 0;
    }
    a { color: inherit; }
    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 26px 0 46px;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 28px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
      font-weight: 850;
      font-size: 18px;
    }
    .mark {
      width: 40px;
      height: 40px;
      border: 1px solid rgba(244, 195, 78, .95);
      background: linear-gradient(135deg, #f4c34e, #5fbf9f 52%, #101316);
      display: grid;
      place-items: center;
      color: #090909;
      font-weight: 900;
      border-radius: 8px;
      flex: none;
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .link, .button-link {
      min-height: 42px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border-radius: 8px;
      padding: 0 15px;
      text-decoration: none;
      font-weight: 760;
      white-space: nowrap;
    }
    .link {
      color: var(--muted);
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, .03);
    }
    .button-link {
      color: #181006;
      background: var(--gold);
      box-shadow: 0 12px 32px rgba(244, 195, 78, .2);
    }
    .button-link.secondary {
      color: var(--text);
      background: rgba(76, 199, 232, .12);
      border: 1px solid rgba(76, 199, 232, .28);
      box-shadow: none;
    }
    [hidden] { display: none !important; }
    .gallery-hero {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(300px, .9fr);
      gap: 18px;
      align-items: stretch;
      margin-bottom: 36px;
    }
    .media-main, .media-stack, .media-card {
      min-width: 0;
    }
    .media-main, .media-card {
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(244, 195, 78, .2), rgba(76, 199, 232, .12)),
        #111316;
      box-shadow: var(--shadow);
    }
    .media-main {
      min-height: 420px;
      padding: 24px;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
    }
    .media-main::before,
    .media-card::before {
      content: "";
      position: absolute;
      inset: 24px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, .12);
      background:
        linear-gradient(120deg, transparent 0 34%, rgba(255, 255, 255, .18) 36% 44%, transparent 47%),
        radial-gradient(circle at 24% 30%, rgba(103, 212, 143, .26), transparent 9rem),
        radial-gradient(circle at 76% 60%, rgba(255, 124, 102, .24), transparent 10rem);
      opacity: .86;
    }
    .media-main::after {
      content: "";
      position: absolute;
      left: 50%;
      top: 50%;
      width: 74px;
      height: 74px;
      transform: translate(-50%, -50%);
      border-radius: 999px;
      background: rgba(8, 9, 11, .72);
      border: 1px solid rgba(255, 255, 255, .26);
      box-shadow: 0 14px 48px rgba(0, 0, 0, .45);
    }
    .play {
      position: absolute;
      left: 50%;
      top: 50%;
      width: 0;
      height: 0;
      transform: translate(-35%, -50%);
      border-top: 16px solid transparent;
      border-bottom: 16px solid transparent;
      border-left: 24px solid var(--gold);
      z-index: 2;
    }
    .media-label {
      position: relative;
      z-index: 3;
      display: inline-flex;
      width: fit-content;
      border: 1px solid rgba(255, 255, 255, .18);
      background: rgba(8, 9, 11, .6);
      border-radius: 8px;
      padding: 9px 12px;
      color: #f7f2ea;
      font-weight: 760;
    }
    .media-stack {
      display: grid;
      gap: 18px;
    }
    .media-card {
      min-height: 201px;
      padding: 18px;
      display: flex;
      align-items: flex-end;
    }
    .media-note {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
      align-self: end;
    }
    .intro {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr);
      gap: 36px;
      align-items: start;
      margin-bottom: 46px;
    }
    .eyebrow {
      color: var(--cyan);
      font-size: 13px;
      font-weight: 820;
      text-transform: uppercase;
      margin-bottom: 12px;
    }
    h1 {
      margin: 0;
      max-width: 850px;
      font-size: clamp(40px, 7vw, 78px);
      line-height: .94;
      letter-spacing: 0;
    }
    h2 {
      margin: 0;
      font-size: clamp(26px, 3vw, 38px);
      letter-spacing: 0;
    }
    .subtitle {
      max-width: 760px;
      margin: 22px 0 0;
      color: #e4dcd2;
      font-size: 20px;
      line-height: 1.55;
    }
    .cta-row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 26px;
    }
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin: 30px 0 44px;
    }
    .feature, .steps, .register-card {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 16px 44px rgba(0, 0, 0, .18);
    }
    .feature strong {
      display: block;
      font-size: 18px;
      margin-bottom: 9px;
    }
    .feature p, .steps p {
      color: var(--muted);
      margin: 0;
      line-height: 1.5;
    }
    .steps {
      display: grid;
      gap: 14px;
    }
    .step {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
    }
    .step span {
      width: 34px;
      height: 34px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: rgba(244, 195, 78, .14);
      color: var(--gold);
      font-weight: 900;
    }
    .register-layout {
      display: grid;
      grid-template-columns: minmax(0, .92fr) minmax(360px, 520px);
      gap: 26px;
      align-items: start;
    }
    .register-copy {
      padding: 20px 0;
    }
    .register-copy p {
      color: #e4dcd2;
      font-size: 19px;
      line-height: 1.55;
      max-width: 620px;
    }
    .form-panel {
      border: 1px solid var(--line);
      background: rgba(17, 19, 22, .94);
      border-radius: 8px;
      padding: 24px;
      box-shadow: var(--shadow);
    }
    label {
      display: block;
      font-weight: 760;
      margin: 16px 0 7px;
    }
    input, select {
      width: 100%;
      height: 46px;
      border: 1px solid rgba(255, 255, 255, .38);
      background: #0b0d0f;
      color: var(--text);
      border-radius: 8px;
      padding: 0 12px;
      font: inherit;
    }
    input:focus, select:focus {
      outline: 2px solid rgba(76, 199, 232, .45);
      border-color: rgba(76, 199, 232, .8);
    }
    .hint {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.35;
    }
    .optional { opacity: .72; }
    button {
      width: 100%;
      min-height: 48px;
      border: 0;
      border-radius: 8px;
      background: var(--gold);
      color: #171009;
      font: inherit;
      font-weight: 850;
      cursor: pointer;
      margin-top: 20px;
    }
    button.secondary {
      margin-top: 8px;
      background: rgba(255, 255, 255, .08);
      color: var(--text);
      border: 1px solid var(--line);
    }
    .result {
      display: none;
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }
    .result.show { display: block; }
    .result-grid {
      display: grid;
      gap: 10px;
    }
    .readonly {
      font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
      font-size: 14px;
    }
    .status {
      min-height: 22px;
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
    }
    .status.error { color: var(--coral); }
    .site-footer {
      margin-top: 56px;
      border-top: 1px solid var(--line);
      padding-top: 24px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 26px;
      color: var(--muted);
    }
    .footer-title {
      color: var(--text);
      font-weight: 820;
      margin-bottom: 8px;
    }
    .footer-list {
      display: grid;
      gap: 8px;
      min-width: 190px;
    }
    .footer-list a, .footer-list span {
      color: var(--muted);
      text-decoration: none;
    }
    .footer-list a:hover { color: var(--text); }
    @media (max-width: 900px) {
      .gallery-hero, .intro, .register-layout { grid-template-columns: 1fr; }
      .feature-grid { grid-template-columns: 1fr; }
      .media-main { min-height: 320px; }
      .site-footer { grid-template-columns: 1fr; }
      h1 { font-size: 44px; }
    }
    @media (max-width: 560px) {
      .shell { width: min(100% - 24px, 1180px); padding-top: 18px; }
      .topbar { align-items: flex-start; }
      .brand { font-size: 16px; }
      .nav-actions { gap: 8px; }
      .link, .button-link { min-height: 38px; padding: 0 11px; }
      .media-main { min-height: 260px; }
      .media-stack { gap: 12px; }
      .media-card { min-height: 150px; }
      h1 { font-size: 38px; }
      .subtitle { font-size: 18px; }
    }
    """


def _seo_head(
    *,
    title: str,
    description: str,
    canonical_url: str,
    lang: str,
) -> str:
    other_lang = "en" if lang == "ru" else "ru"
    other_url = canonical_url.replace(f"lang={lang}", f"lang={other_lang}")
    default_url = canonical_url.replace(f"lang={lang}", "lang=ru")
    return f"""
  <meta name="description" content="{escape(description)}">
  <link rel="canonical" href="{escape(canonical_url)}">
  <link rel="alternate" hreflang="{lang}" href="{escape(canonical_url)}">
  <link rel="alternate" hreflang="{other_lang}" href="{escape(other_url)}">
  <link rel="alternate" hreflang="x-default" href="{escape(default_url)}">
  <meta property="og:site_name" content="The Bazaar Live Board">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{escape(canonical_url)}">
  <meta property="og:image" content="https://thebazaar-twitch.online/image/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:locale" content="ru_RU">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="https://thebazaar-twitch.online/image/og-image.png">
  <meta name="twitter:image:alt" content="The Bazaar Live Board - Twitch Extension companion for streamers">
  <meta name="twitter:title" content="{escape(title)}">
  <meta name="twitter:description" content="{escape(description)}">"""


def _nav(*, lang: str, current: str, public_url: str) -> str:
    text = TEXT[lang]
    other_lang = "en" if lang == "ru" else "ru"
    lang_path = "/register" if current == "register" else "/new"
    register_url = f"{public_url.rstrip('/')}/register?lang={lang}"
    new_url = f"{public_url.rstrip('/')}/new?lang={lang}"
    lang_url = f"{lang_path}?lang={other_lang}"
    cta = (
        f'<a class="button-link" href="{escape(register_url)}">{escape(text["register_cta"])}</a>'
        if current != "register"
        else f'<a class="link" href="{escape(new_url)}">{escape(text["footer_site"])}</a>'
    )
    download = (
        f'<a class="button-link secondary" href="{escape(STREAMER_APP_DOWNLOAD_URL)}">'
        f'{escape(text["download_cta"])}</a>'
        if SHOW_STREAMER_APP_DOWNLOAD
        else (
            f'<a class="button-link secondary" href="{escape(STREAMER_APP_DOWNLOAD_URL)}" hidden>'
            f'{escape(text["download_cta"])}</a>'
        )
    )
    return f"""
    <nav class="topbar">
      <a class="brand" href="{escape(new_url)}" aria-label="{escape(text["brand"])}">
        <img src="/image/logo.png" alt="The Bazaar Live Board" class="brand-logo" height="32"><span>{escape(text["brand"])}</span>
      </a>
      <div class="nav-actions">
        {download}
        {cta}
        <a class="link" href="{escape(lang_url)}">{escape(text["lang_switch"])}</a>
      </div>
    </nav>
    """


def _footer(*, lang: str, public_url: str) -> str:
    text = TEXT[lang]
    new_url = f"{public_url.rstrip('/')}/new?lang={lang}"
    register_url = f"{public_url.rstrip('/')}/register?lang={lang}"
    email = escape(CONTACT_EMAIL)
    if DISCORD_URL:
        discord = (
            f'<a href="{escape(DISCORD_URL)}" rel="noopener noreferrer">'
            f'{escape(text["footer_discord"])}</a>'
        )
    else:
        discord = f'<span>{escape(text["footer_discord_soon"])}</span>'
    download = (
        f'<a href="{escape(STREAMER_APP_DOWNLOAD_URL)}">'
        f'{escape(text["footer_release"])}</a>'
        if SHOW_STREAMER_APP_DOWNLOAD
        else (
            f'<a href="{escape(STREAMER_APP_DOWNLOAD_URL)}" hidden>'
            f'{escape(text["footer_release"])}</a>'
        )
    )
    return f"""
    <footer class="site-footer">
      <div>
        <div class="footer-title">{escape(text["brand"])}</div>
        <div>{escape(text["footer_product"])}</div>
      </div>
      <div class="footer-list">
        <div class="footer-title">{escape(text["footer_contacts"])}</div>
        <a href="mailto:{email}">{escape(text["footer_email"])}: {email}</a>
        {discord}
      </div>
      <div class="footer-list">
        <div class="footer-title">{escape(text["footer_links"])}</div>
        <a href="{escape(new_url)}">{escape(text["footer_site"])}</a>
        <a href="{escape(register_url)}">{escape(text["footer_register"])}</a>
        {download}
      </div>
    </footer>
    """


def render_landing_page(*, language: str, public_url: str) -> str:
    lang = supported_language(language)
    text = TEXT[lang]
    canonical_url = f"{public_url.rstrip('/')}/new?lang={lang}"
    title = text["brand"]
    description = text["landing_subtitle"]
    register_url = f"{public_url.rstrip('/')}/register?lang={lang}"
    download = (
        f'<a class="button-link secondary" href="{escape(STREAMER_APP_DOWNLOAD_URL)}">'
        f'{escape(text["download_cta"])}</a>'
        if SHOW_STREAMER_APP_DOWNLOAD
        else (
            f'<a class="button-link secondary" href="{escape(STREAMER_APP_DOWNLOAD_URL)}" hidden>'
            f'{escape(text["download_cta"])}</a>'
        )
    )
    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <link rel="icon" type="image/png" sizes="48x48" href="/image/favicon-48x48.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/image/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/image/favicon-16x16.png">
  <link rel="icon" href="/image/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/image/apple-touch-icon.png">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {_seo_head(title=title, description=description, canonical_url=canonical_url, lang=lang)}
  <style>{_styles()}</style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "The Bazaar Live Board",
    "applicationCategory": "GameApplication",
    "operatingSystem": "Windows",
    "description": "Companion для стримеров The Bazaar - распознавание карточек и Twitch Extension оверлей",
    "offers": {{
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    }}
  }}
  </script>
</head>
<body>
  <main class="shell">
    {_nav(lang=lang, current="new", public_url=public_url)}

    <section class="gallery-hero" aria-label="Gallery">
      <div class="media-main">
        <span class="play" aria-hidden="true"></span>
        <span class="media-label">{escape(text["gallery_video"])}</span>
      </div>
      <div class="media-stack">
        <div class="media-card"><span class="media-label">{escape(text["gallery_screen_1"])}</span></div>
        <div class="media-card"><span class="media-label">{escape(text["gallery_screen_2"])}</span></div>
        <div class="media-note">{escape(text["gallery_note"])}</div>
      </div>
    </section>

    <section class="intro">
      <div>
        <div class="eyebrow">{escape(text["landing_eyebrow"])}</div>
        <h1>{escape(text["landing_title"])}</h1>
        <p class="subtitle">{escape(text["landing_subtitle"])}</p>
        <div class="cta-row">
          <a class="button-link" href="{escape(register_url)}">{escape(text["register_cta"])}</a>
          {download}
        </div>
      </div>
      <div class="steps">
        <h2>{escape(text["how_title"])}</h2>
        <div class="step"><span>1</span><p>{escape(text["how_1"])}</p></div>
        <div class="step"><span>2</span><p>{escape(text["how_2"])}</p></div>
        <div class="step"><span>3</span><p>{escape(text["how_3"])}</p></div>
      </div>
    </section>

    <section class="feature-grid">
      <article class="feature">
        <strong>{escape(text["feature_1_title"])}</strong>
        <p>{escape(text["feature_1_text"])}</p>
      </article>
      <article class="feature">
        <strong>{escape(text["feature_2_title"])}</strong>
        <p>{escape(text["feature_2_text"])}</p>
      </article>
      <article class="feature">
        <strong>{escape(text["feature_3_title"])}</strong>
        <p>{escape(text["feature_3_text"])}</p>
      </article>
    </section>

    {_footer(lang=lang, public_url=public_url)}
  </main>
</body>
</html>"""


def render_registration_page(
    *,
    language: str,
    public_url: str,
    api_url: str | None = None,
) -> str:
    lang = supported_language(language)
    text = TEXT[lang]
    api_base_url = (api_url or public_url).rstrip("/")
    canonical_url = f"{public_url.rstrip('/')}/register?lang={lang}"
    title = text["register_page_title"]
    description = text["register_subtitle"]

    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <link rel="icon" type="image/png" sizes="48x48" href="/image/favicon-48x48.png">
  <link rel="icon" type="image/png" sizes="32x32" href="/image/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/image/favicon-16x16.png">
  <link rel="icon" href="/image/favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="/image/apple-touch-icon.png">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {_seo_head(title=title, description=description, canonical_url=canonical_url, lang=lang)}
  <style>{_styles()}</style>
</head>
<body>
  <main class="shell">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "WebSite",
      "name": "The Bazaar Live Board",
      "url": "https://thebazaar-twitch.online"
    }}
    </script>
    {_nav(lang=lang, current="register", public_url=public_url)}

    <section class="register-layout">
      <div class="register-copy">
        <div class="eyebrow">{escape(text["landing_eyebrow"])}</div>
        <h1>{escape(text["register_title"])}</h1>
        <p>{escape(text["register_subtitle"])}</p>
      </div>

      <form class="form-panel" id="register-form">
        <h2>{escape(text["form_title"])}</h2>

        <label for="channelLogin">{escape(text["channel_login"])}</label>
        <input id="channelLogin" name="channelLogin" autocomplete="nickname" required>
        <div class="hint">{escape(text["channel_hint"])}</div>

        <label for="email">{escape(text["email"])}</label>
        <input id="email" name="email" type="email" autocomplete="email" required>
        <div class="hint">{escape(text["email_hint"])}</div>

        <label for="language">{escape(text["language"])}</label>
        <select id="language" name="language">
          <option value="ru" {"selected" if lang == "ru" else ""}>Русский</option>
          <option value="en" {"selected" if lang == "en" else ""}>English</option>
        </select>

        <button id="submit-button" type="submit">{escape(text["submit"])}</button>
        <div class="status" id="status"></div>

        <section class="result" id="result">
          <h2>{escape(text["result_title"])}</h2>
          <p class="hint">{escape(text["result_note"])}</p>
          <div class="result-grid">
            <label for="resultChannel">{escape(text["channel_label"])}</label>
            <input class="readonly" id="resultChannel" readonly>
            <button class="secondary" type="button" data-copy="resultChannel">{escape(text["copy"])}</button>
            <label for="resultToken">{escape(text["token_label"])}</label>
            <input class="readonly" id="resultToken" readonly>
            <button class="secondary" type="button" data-copy="resultToken">{escape(text["copy"])}</button>
          </div>
          <p class="hint">{escape(text["open_app"])}</p>
        </section>
      </form>
    </section>

    {_footer(lang=lang, public_url=public_url)}
  </main>

  <script>
    const text = {{
      registering: {text["registering"]!r},
      copied: {text["copied"]!r},
      failed: {text["failed"]!r},
      emailSent: {text["email_sent"]!r},
      emailNotSent: {text["email_not_sent"]!r}
    }};
    const form = document.querySelector("#register-form");
    const statusNode = document.querySelector("#status");
    const submitButton = document.querySelector("#submit-button");
    const result = document.querySelector("#result");
    const apiBaseUrl = {api_base_url!r};

    function setStatus(message, isError = false) {{
      statusNode.textContent = message;
      statusNode.classList.toggle("error", isError);
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      setStatus(text.registering);
      submitButton.disabled = true;
      result.classList.remove("show");

      const body = {{
        channelLogin: form.channelLogin.value.trim(),
        email: form.email.value.trim(),
        language: form.language.value
      }};

      try {{
        const response = await fetch(`${{apiBaseUrl}}/api/register`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(body)
        }});
        const data = await response.json();
        if (!response.ok) {{
          const detail = data.detail && (data.detail.error || data.detail);
          throw new Error(detail || text.failed);
        }}
        document.querySelector("#resultChannel").value = data.channelLogin || data.channelId;
        document.querySelector("#resultToken").value = data.companionToken;
        result.classList.add("show");
        setStatus(data.emailSent ? text.emailSent : text.emailNotSent);
      }} catch (error) {{
        setStatus(`${{text.failed}}: ${{error.message}}`, true);
      }} finally {{
        submitButton.disabled = false;
      }}
    }});

    document.querySelectorAll("[data-copy]").forEach((button) => {{
      button.addEventListener("click", async () => {{
        const input = document.querySelector(`#${{button.dataset.copy}}`);
        input.select();
        await navigator.clipboard.writeText(input.value);
        setStatus(text.copied);
      }});
    }});
  </script>
</body>
</html>"""
