-module(kpproton_resend_adapter).

%% FILE: apps/kpproton_portal/src/integrations/resend/kpproton_resend_adapter.erl
%% VERSION: 1.1.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Define the Resend API adapter contract for magic-link email delivery.
%%   SCOPE: Build branded request payloads, map provider status codes to typed failures, and expose a send_magic_link/4 entry point.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-EMAIL, M-WEB-API
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   build_payload/3 - constructs the Resend email payload
%%   map_provider_error/1 - normalizes status codes into typed failures
%%   send_magic_link/4 - returns a placeholder request contract for later HTTP wiring
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.1.0 - Added template-driven subject, HTML, and text email generation for the magic-link flow.
%% END_CHANGE_SUMMARY

-export([build_payload/3, map_provider_error/1, send_magic_link/4]).

%% START_BLOCK_BUILD_REQUEST
build_payload(ToEmail, VerifyUrl, FromEmail) ->
    io:format("[M-EMAIL][send_magic_link][BUILD_REQUEST]~n", []),
    #{subject := Subject, html := Html, text := Text} =
        kpproton_email_template:build_magic_link_email(kpproton_runtime:base_domain(), VerifyUrl, ToEmail),
    #{
        from => FromEmail,
        to => [ToEmail],
        subject => Subject,
        html => Html,
        text => Text
    }.
%% END_BLOCK_BUILD_REQUEST

%% START_BLOCK_MAP_PROVIDER_ERROR
map_provider_error(401) ->
    io:format("[M-EMAIL][send_magic_link][MAP_PROVIDER_ERROR]~n", []),
    {error, invalid_api_key};
map_provider_error(429) ->
    io:format("[M-EMAIL][send_magic_link][MAP_PROVIDER_ERROR]~n", []),
    {error, rate_limited};
map_provider_error(Status) when Status >= 500 ->
    io:format("[M-EMAIL][send_magic_link][MAP_PROVIDER_ERROR]~n", []),
    {error, provider_unavailable};
map_provider_error(timeout) ->
    io:format("[M-EMAIL][send_magic_link][MAP_PROVIDER_ERROR]~n", []),
    {error, timeout};
map_provider_error(_) ->
    io:format("[M-EMAIL][send_magic_link][MAP_PROVIDER_ERROR]~n", []),
    {error, unexpected_response}.
%% END_BLOCK_MAP_PROVIDER_ERROR

%% START_BLOCK_POST_RESEND
send_magic_link(ToEmail, VerifyUrl, ApiKey, FromEmail) ->
    io:format("[M-EMAIL][send_magic_link][POST_RESEND]~n", []),
    case ApiKey of
        <<>> ->
            {error, invalid_api_key};
        _ ->
            Payload = jsx:encode(build_payload(ToEmail, VerifyUrl, FromEmail)),
            Headers = [
                {"authorization", "Bearer " ++ binary_to_list(ApiKey)},
                {"content-type", "application/json"}
            ],
            case httpc:request(
                     post,
                     {"https://api.resend.com/emails", Headers, "application/json", Payload},
                     [{timeout, 10000}],
                     [{body_format, binary}]
                 ) of
                {ok, {{_, Status, _}, _RespHeaders, RespBody}} when Status >= 200, Status < 300 ->
                    {ok, RespBody};
                {ok, {{_, Status, _}, _RespHeaders, _RespBody}} ->
                    map_provider_error(Status);
                {error, timeout} ->
                    map_provider_error(timeout);
                {error, _Reason} ->
                    {error, provider_unavailable}
            end
    end.
%% END_BLOCK_POST_RESEND
