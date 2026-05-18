%% coding: utf-8
-module(kpproton_email_template).

%% FILE: apps/kpproton_portal/src/integrations/resend/kpproton_email_template.erl
%% VERSION: 1.2.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Render readable, branded magic-link email content for Resend delivery.
%%   SCOPE: Generate subject, HTML body, and plain-text fallback for verification emails.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-EMAIL-TEMPLATE, M-EMAIL
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   build_magic_link_email/3 - returns subject, html, and text content for the verification email
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.2.0 - Added rollout guidance that only the freshest reissued tg://proxy link remains valid after access-hardening updates.
%% END_CHANGE_SUMMARY

-export([build_magic_link_email/3]).

u(Text) ->
    unicode:characters_to_binary(Text).

%% START_BLOCK_BUILD_MAGIC_LINK_EMAIL
build_magic_link_email(BaseDomain, VerifyUrl, ToEmail) ->
    Subject = u("Подтвердите email и получите персональный MTProto-прокси"),
    Html = iolist_to_binary([
        <<"<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">">>,
        <<"<title>KPprotoN</title></head><body style=\"margin:0;padding:0;background:#f3efe7;font-family:IBM Plex Sans,Segoe UI,sans-serif;color:#1a1d23;\">">>,
        <<"<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"padding:32px 16px;background:#f3efe7;\"><tr><td align=\"center\">">>,
        <<"<table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:620px;background:#fffdf8;border-radius:24px;overflow:hidden;box-shadow:0 18px 50px rgba(27,24,19,.12);\">">>,
        <<"<tr><td style=\"padding:28px 32px;background:linear-gradient(135deg,#c75929,#933915);color:#fff8f0;\">">>,
        <<"<div style=\"font-size:12px;letter-spacing:.18em;text-transform:uppercase;opacity:.88;\">KPprotoN</div>">>,
        <<"<h1 style=\"margin:12px 0 0;font-size:30px;line-height:1.05;\">">>, u("Подтвердите email"), <<"</h1>">>,
        <<"<p style=\"margin:12px 0 0;font-size:16px;line-height:1.6;color:#ffe9df;\">">>,
        u("Это письмо нужно, чтобы выдать вам персональную ссылку на MTProto-прокси для Telegram."),
        <<"</p>">>,
        <<"</td></tr><tr><td style=\"padding:28px 32px;\">">>,
        <<"<p style=\"margin:0 0 16px;font-size:16px;line-height:1.7;color:#424854;\">">>,
        u("Для адреса <strong>"), ToEmail, u("</strong> был запрошен доступ к прокси на домене <strong>"), BaseDomain, u("</strong>."),
        <<"</p>">>,
        <<"<p style=\"margin:0 0 24px;font-size:16px;line-height:1.7;color:#424854;\">">>,
        u("Нажмите кнопку ниже. После подтверждения откроется страница, где можно сразу скопировать и вставить готовую ссылку в Telegram."),
        <<"</p>">>,
        <<"<p style=\"margin:0 0 24px;font-size:14px;line-height:1.7;color:#5d6470;\">">>,
        u("Если вы уже получали прокси раньше, используйте только самую свежую ссылку из этого письма: после обновления безопасности старые tg://proxy-ссылки отключаются."),
        <<"</p>">>,
        <<"<p style=\"margin:0 0 24px;\"><a href=\"">>, VerifyUrl, <<"\" style=\"display:inline-block;padding:15px 22px;border-radius:999px;background:#1d7a49;color:#fff;text-decoration:none;font-weight:700;\">">>,
        u("Получить прокси"),
        <<"</a></p>">>,
        <<"<p style=\"margin:0 0 12px;font-size:14px;line-height:1.7;color:#5d6470;\">">>,
        u("Если кнопка не работает, откройте эту ссылку вручную:"),
        <<"</p>">>,
        <<"<p style=\"margin:0 0 24px;font-size:14px;line-height:1.7;word-break:break-word;\"><a href=\"">>, VerifyUrl, <<"\" style=\"color:#933915;\">">>, VerifyUrl, <<"</a></p>">>,
        <<"<p style=\"margin:0;font-size:13px;line-height:1.7;color:#7a828f;\">">>,
        u("Если вы не запрашивали прокси, просто проигнорируйте это письмо."),
        <<"</p>">>,
        <<"</td></tr></table></td></tr></table></body></html>">>
    ]),
    Text = iolist_to_binary([
        u("KPprotoN\n\n"),
        u("Подтвердите email и получите персональный MTProto-прокси.\n\n"),
        u("Для адреса "), ToEmail, u(" был запрошен доступ к прокси на домене "), BaseDomain, u(".\n\n"),
        u("Если вы уже получали прокси раньше, используйте только самую свежую ссылку из этого письма: после обновления безопасности старые tg://proxy-ссылки отключаются.\n\n"),
        u("Откройте ссылку:\n"), VerifyUrl, <<"\n\n">>,
        u("Если вы не запрашивали прокси, просто проигнорируйте это письмо.\n")
    ]),
    #{
        subject => Subject,
        html => Html,
        text => Text
    }.
%% END_BLOCK_BUILD_MAGIC_LINK_EMAIL
