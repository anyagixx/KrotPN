%% coding: utf-8
-module(kpproton_verify_handler).
-behaviour(cowboy_handler).

%% FILE: apps/kpproton_portal/src/http/kpproton_verify_handler.erl
%% VERSION: 1.6.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Render the verification-side HTML response contract for consumed tokens and issued proxy links.
%%   SCOPE: Invalid token handling, consumed-token success rendering, and operator-safe error HTML mapping.
%%   DEPENDS: M-TOKEN, M-PROXY-ISSUE
%%   LINKS: M-WEB-API
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   render_verify_result/1 - maps verification outcomes to HTML result pages
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.6.0 - Added rollout messaging that `/verify` reissues the canonical derived credential and supersedes older tg://proxy links.
%% END_CHANGE_SUMMARY

-export([init/2, render_verify_result/1]).

init(Req0, State) ->
    QsVals = cowboy_req:parse_qs(Req0),
    Token = proplists:get_value(<<"token">>, QsVals, undefined),
    Html =
        case Token of
            undefined ->
                render_verify_result(undefined);
            _ ->
                case kpproton_runtime:consume_token(Token) of
                    {ok, #{email := Email}} ->
                        Path = kpproton_runtime:registry_path(),
                        {ok, RegistryHandle} = kpproton_registry:open_registry(Path),
                        Existing = kpproton_registry:lookup_user(Email, RegistryHandle),
                        Assignment = kpproton_proxy_issue:issue_proxy_for_email(
                            Email,
                            kpproton_runtime:base_domain(),
                            kpproton_runtime:proxy_secret(),
                            kpproton_runtime:proxy_secret_salt(),
                            Existing,
                            kpproton_runtime:proxy_port()
                        ),
                        Result =
                            case kpproton_proxy_bridge:apply_domain_policy(maps:get(sni, Assignment)) of
                                ok ->
                                    ok = kpproton_registry:save_user(Email, Assignment, RegistryHandle),
                                    render_verify_result(Assignment);
                                {error, bridge_reason} ->
                                    render_verify_result({error, bridge_reason});
                                {error, Reason} ->
                                    render_verify_result({error, Reason})
                            end,
                        ok = kpproton_registry:close_registry(RegistryHandle),
                        Result;
                    {error, expired} ->
                        render_verify_result({error, expired});
                    _ ->
                        render_verify_result(undefined)
                end
        end,
    Req = cowboy_req:reply(200, #{<<"content-type">> => <<"text/html; charset=utf-8">>}, Html, Req0),
    {ok, Req, State}.

u(Text) ->
    unicode:characters_to_binary(Text).

html_escape(Value) when is_binary(Value) ->
    EscapedAmp = binary:replace(Value, <<"&">>, <<"&amp;">>, [global]),
    EscapedLt = binary:replace(EscapedAmp, <<"<">>, <<"&lt;">>, [global]),
    EscapedGt = binary:replace(EscapedLt, <<">">>, <<"&gt;">>, [global]),
    EscapedQuote = binary:replace(EscapedGt, <<"\"">>, <<"&quot;">>, [global]),
    binary:replace(EscapedQuote, <<"'">>, <<"&#39;">>, [global]).

decode_query_pairs(TgLink) ->
    case binary:split(TgLink, <<"?">>) of
        [_Prefix, Query] ->
            lists:foldl(
              fun(Pair, Acc) ->
                  case binary:split(Pair, <<"=">>) of
                      [Key, Value] ->
                          Acc#{Key => Value};
                      _ ->
                          Acc
                  end
              end,
              #{},
              binary:split(Query, <<"&">>, [global])
            );
        _ ->
            #{}
    end.

render_layout(Title, Subtitle, BodyBlocks) ->
    iolist_to_binary([
        <<"<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">">>,
        <<"<title>KPprotoN</title><link rel=\"stylesheet\" href=\"/static/styles.css\"></head><body>">>,
        <<"<main class=\"page-shell result-shell\"><section class=\"page-card result-panel\">">>,
        <<"<div class=\"eyebrow\">KPprotoN</div>">>,
        <<"<h1>">>, Title, <<"</h1>">>,
        <<"<p class=\"lead\">">>, Subtitle, <<"</p>">>,
        BodyBlocks,
        <<"</section></main><script src=\"/static/verify.js\" defer></script></body></html>">>
    ]).

render_error_page(Title, Message) ->
    render_layout(
      Title,
      Message,
      [<<"<div class=\"result-error\">">>,
       u("Если вы открыли старое письмо, запросите новую ссылку на главной странице."),
       <<"</div>">>]
    ).

render_result_field(Label, Id, Value, ButtonLabel) ->
    SafeValue = html_escape(Value),
    [
        <<"<article class=\"result-card\"><div class=\"result-field\">">>,
        <<"<span class=\"result-label\">">>, Label, <<"</span>">>,
        <<"<code class=\"result-value\" id=\"">>, Id, <<"\" data-copy-value=\"">>, SafeValue, <<"\">">>, SafeValue, <<"</code>">>,
        <<"<button type=\"button\" class=\"copy-button\" data-copy=\"">>, Id, <<"\">">>, ButtonLabel, <<"</button>">>,
        <<"</div></article>">>
    ].

%% START_BLOCK_RENDER_RESULT
render_verify_result(undefined) ->
    io:format("[M-WEB-API][verify_token][RENDER_RESULT]~n", []),
    render_error_page(
      u("Ссылка недействительна"),
      u("Токен не найден или уже был использован.")
    );
render_verify_result({error, expired}) ->
    io:format("[M-WEB-API][verify_token][RENDER_RESULT]~n", []),
    render_error_page(
      u("Срок действия ссылки истёк"),
      u("Запросите новую ссылку на получение прокси.")
    );
render_verify_result(#{email := Email, tg_link := TgLink, sni := SniDomain}) ->
    io:format("[M-WEB-API][verify_token][CONSUME_TOKEN]~n", []),
    io:format("[M-WEB-API][verify_token][RENDER_RESULT]~n", []),
    QueryPairs = decode_query_pairs(TgLink),
    Server = maps:get(<<"server">>, QueryPairs, SniDomain),
    Port = maps:get(<<"port">>, QueryPairs, <<"443">>),
    Secret = maps:get(<<"secret">>, QueryPairs, <<>>),
    render_layout(
      u("Прокси готов"),
      u("Откройте ссылку в Telegram или скопируйте данные для ручного добавления MTProto-прокси."),
      iolist_to_binary([
          <<"<div class=\"result-actions\">">>,
          <<"<a class=\"primary-link\" href=\"">>, html_escape(TgLink), <<"\">">>, u("Открыть в Telegram"), <<"</a>">>,
          <<"<button type=\"button\" class=\"copy-button\" data-copy=\"proxy-link\">">>, u("Скопировать tg://proxy"), <<"</button></div>">>,
          <<"<article class=\"result-card\"><div class=\"result-field\">">>,
          <<"<span class=\"result-label\">tg://proxy</span>">>,
          <<"<code class=\"result-value\" id=\"proxy-link\" data-copy-value=\"">>, html_escape(TgLink), <<"\">">>, html_escape(TgLink), <<"</code>">>,
          <<"</div></article>">>,
          <<"<div class=\"result-grid\">">>,
          render_result_field(u("Сервер"), <<"manual-server">>, Server, u("Скопировать сервер")),
          render_result_field(u("Порт"), <<"manual-port">>, Port, u("Скопировать порт")),
          render_result_field(u("Secret"), <<"manual-secret">>, Secret, u("Скопировать secret")),
          <<"</div>">>,
          <<"<article class=\"result-card\"><div class=\"result-field\">">>,
          <<"<span class=\"result-label\">Email</span><code class=\"result-value\">">>, html_escape(Email), <<"</code></div>">>,
          <<"<div class=\"result-field\"><span class=\"result-label\">SNI</span><code class=\"result-value\">">>, html_escape(SniDomain), <<"</code></div></article>">>,
          <<"<article class=\"result-card\"><div class=\"result-note\"><strong>">>,
          u("Используйте только эту ссылку и этот Secret: более ранние выданные tg://proxy-ссылки считаются устаревшими."),
          <<"<br><br><strong>">>,
          u("Ручная настройка в Telegram:"),
          <<"</strong> ">>,
          u("откройте Telegram → Настройки → Данные и память → Прокси → Добавить прокси → MTProto."),
          <<"<br><br>">>,
          u("Вставьте "),
          <<"<strong>">>, u("Сервер"), <<"</strong>">>,
          u(" в поле Server, "),
          <<"<strong>">>, u("Порт"), <<"</strong>">>,
          u(" в поле Port и "),
          <<"<strong>Secret</strong>">>,
          u(" в поле Secret. Если Telegram уже открыл ссылку "),
          <<"<code>tg://proxy</code>">>,
          u(", вручную ничего вводить не нужно."),
          <<"</div></article>">>
      ])
    );
render_verify_result({error, mtproto_policy_table_unavailable}) ->
    io:format("[M-WEB-API][verify_token][RENDER_RESULT]~n", []),
    render_error_page(
      u("Прокси-движок недоступен"),
      u("Попробуйте ещё раз через несколько минут.")
    );
render_verify_result(_) ->
    io:format("[M-WEB-API][verify_token][RENDER_RESULT]~n", []),
    render_error_page(
      u("Ошибка верификации"),
      u("Не удалось подготовить прокси. Попробуйте запросить новую ссылку.")
    ).
%% END_BLOCK_RENDER_RESULT
