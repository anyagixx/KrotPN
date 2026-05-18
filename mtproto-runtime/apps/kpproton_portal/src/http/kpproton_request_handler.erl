%% coding: utf-8
-module(kpproton_request_handler).
-behaviour(cowboy_handler).

%% FILE: apps/kpproton_portal/src/http/kpproton_request_handler.erl
%% VERSION: 1.1.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Define the request-side HTTP contract for email intake and health checks.
%%   SCOPE: Email validation, accepted/error JSON payloads, and placeholder hooks for token and email dispatch.
%%   DEPENDS: M-TOKEN, M-EMAIL
%%   LINKS: M-WEB-API, M-WEB-UI
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   validate_email/1 - validates request email format
%%   handle_request/1 - returns accepted or error payload for POST /api/request
%%   health_response/0 - returns lightweight health payload
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.1.0 - Added explicit UTF-8 source encoding so accepted and error payloads keep readable Cyrillic text.
%% END_CHANGE_SUMMARY

-export([init/2, validate_email/1, handle_request/1, health_response/0]).

u(Text) ->
    unicode:characters_to_binary(Text).

%% START_BLOCK_VALIDATE_INPUT
validate_email(Email) when is_binary(Email) ->
    case re:run(Email, <<"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$">>, [{capture, none}]) of
        match -> ok;
        nomatch -> {error, invalid_email}
    end;
validate_email(_) ->
    {error, invalid_email}.
%% END_BLOCK_VALIDATE_INPUT

%% START_BLOCK_DISPATCH_EMAIL
handle_request(Email) ->
    io:format("[M-WEB-API][request_email][VALIDATE_INPUT]~n", []),
    case validate_email(Email) of
        ok ->
            io:format("[M-WEB-API][request_email][DISPATCH_EMAIL]~n", []),
            #{
                status => accepted,
                message => u("Проверьте почту"),
                next_step => <<"Open the magic link from your email">>
            };
        {error, invalid_email} ->
            #{
                status => error,
                error => u("Введите корректный email")
            }
    end.
%% END_BLOCK_DISPATCH_EMAIL

%% START_BLOCK_HTTP_INIT
init(Req0, State) ->
    {ok, Body, Req1} = cowboy_req:read_body(Req0),
    Response =
        case decode_email(Body) of
            {ok, Email} ->
                case validate_email(Email) of
                    ok ->
                        case kpproton_runtime:create_token(Email) of
                            {ok, Token, _Record} ->
                                VerifyUrl = iolist_to_binary([
                                    <<"https://">>,
                                    kpproton_runtime:base_domain(),
                                    <<"/verify?token=">>,
                                    Token
                                ]),
                                case kpproton_resend_adapter:send_magic_link(
                                         Email,
                                         VerifyUrl,
                                         kpproton_runtime:resend_api_key(),
                                         kpproton_runtime:resend_from()) of
                                    {ok, _ProviderResponse} ->
                                        handle_request(Email);
                                    {error, invalid_api_key} ->
                                        #{status => error, error => u("Ошибка отправки: проверьте RESEND_API_KEY")};
                                    {error, _} ->
                                        #{status => error, error => u("Не удалось отправить письмо. Попробуйте позже.")}
                                end;
                            {error, _} ->
                                #{status => error, error => u("Не удалось создать токен подтверждения")}
                        end;
                    {error, invalid_email} ->
                        #{status => error, error => u("Введите корректный email")}
                end;
            error ->
                #{status => error, error => u("Некорректный JSON payload")}
        end,
    StatusCode = case maps:get(status, Response) of accepted -> 202; _ -> 400 end,
    Req = cowboy_req:reply(
        StatusCode,
        #{<<"content-type">> => <<"application/json">>},
        jsx:encode(Response),
        Req1
    ),
    {ok, Req, State}.
%% END_BLOCK_HTTP_INIT

%% START_BLOCK_HEALTH
health_response() ->
    #{
        status => <<"ok">>,
        service => <<"kpproton-web-api">>
    }.
%% END_BLOCK_HEALTH

decode_email(Body) ->
    try jsx:decode(Body, [return_maps]) of
        #{<<"email">> := Email} when is_binary(Email) -> {ok, Email};
        _ -> error
    catch
        _:_ -> error
    end.
