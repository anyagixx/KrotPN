%% FILE: src/kpproton_policy_handler.erl
%% VERSION: 1.1.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Expose a token-protected local HTTP bridge for KrotPN MTProto policy apply/revoke and telemetry operations.
%%   SCOPE: Authenticate local bridge requests, validate issued SNI domains, call mtproto policy table hooks, expose safe telemetry, and return safe JSON.
%%   DEPENDS: M-PROXY-BRIDGE, M-CONFIG
%%   LINKS: M-PROXY-BRIDGE, M-RELEASE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   init/2 - Cowboy handler entry for apply, revoke, health, telemetry snapshot, and telemetry drain operations
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.1.0 - Added Phase-42 private telemetry snapshot/drain endpoints.
%%   LAST_CHANGE: v1.0.0 - Added KrotPN live MTProto policy bridge endpoint.
%% END_CHANGE_SUMMARY

-module(kpproton_policy_handler).
-behaviour(cowboy_handler).

-export([init/2]).

%% START_BLOCK_HANDLER_ENTRY
init(Req0, #{operation := health} = State) ->
    case authorized(Req0) of
        true ->
            reply_json(200, kpproton_proxy_bridge:health(), Req0, State);
        false ->
            reply_json(401, #{status => <<"unauthorized">>}, Req0, State)
    end;
init(Req0, #{operation := telemetry_snapshot} = State) ->
    Method = cowboy_req:method(Req0),
    case {Method, authorized(Req0)} of
        {<<"GET">>, true} ->
            reply_json(200, kpproton_usage_telemetry:snapshot(), Req0, State);
        {<<"GET">>, false} ->
            reply_json(401, #{status => <<"unauthorized">>}, Req0, State);
        _ ->
            reply_json(405, #{status => <<"method_not_allowed">>}, Req0, State)
    end;
init(Req0, #{operation := telemetry_drain} = State) ->
    Method = cowboy_req:method(Req0),
    case {Method, authorized(Req0)} of
        {<<"GET">>, true} ->
            {Cursor, Limit} = telemetry_query(Req0),
            reply_json(200, kpproton_usage_telemetry:drain(Cursor, Limit), Req0, State);
        {<<"GET">>, false} ->
            reply_json(401, #{status => <<"unauthorized">>}, Req0, State);
        _ ->
            reply_json(405, #{status => <<"method_not_allowed">>}, Req0, State)
    end;
init(Req0, #{operation := Operation} = State) ->
    Method = cowboy_req:method(Req0),
    case {Method, authorized(Req0)} of
        {<<"POST">>, true} ->
            handle_policy_request(Operation, Req0, State);
        {<<"POST">>, false} ->
            reply_json(401, #{status => <<"unauthorized">>}, Req0, State);
        _ ->
            reply_json(405, #{status => <<"method_not_allowed">>}, Req0, State)
    end.
%% END_BLOCK_HANDLER_ENTRY

%% START_BLOCK_POLICY_REQUEST
handle_policy_request(Operation, Req0, State) ->
    case read_policy_payload(Req0) of
        {ok, Sni, Req1} ->
            case valid_sni(Sni) of
                true ->
                    apply_operation(Operation, Sni, Req1, State);
                false ->
                    reply_json(422, #{status => <<"invalid_sni">>}, Req1, State)
            end;
        {error, Code, Req1} ->
            reply_json(400, #{status => Code}, Req1, State)
    end.

apply_operation(apply, Sni, Req, State) ->
    case kpproton_proxy_bridge:apply_domain_policy(Sni) of
        ok ->
            reply_json(200, #{status => <<"applied">>, sni => mask_sni(Sni)}, Req, State);
        {error, Reason} ->
            reply_json(503, #{status => <<"degraded">>, failure_code => atom_to_binary(Reason)}, Req, State)
    end;
apply_operation(revoke, Sni, Req, State) ->
    case kpproton_proxy_bridge:revoke_domain_policy(Sni) of
        ok ->
            reply_json(200, #{status => <<"revoked">>, sni => mask_sni(Sni)}, Req, State);
        {error, Reason} ->
            reply_json(503, #{status => <<"degraded">>, failure_code => atom_to_binary(Reason)}, Req, State)
    end.
%% END_BLOCK_POLICY_REQUEST

%% START_BLOCK_VALIDATE_REQUEST
authorized(Req) ->
    Expected = policy_token(),
    Provided = cowboy_req:header(<<"x-krotpn-mtproto-token">>, Req, <<>>),
    Expected =/= <<>> andalso Provided =:= Expected.

policy_token() ->
    case os:getenv("KROTPN_MTPROTO_POLICY_TOKEN") of
        false -> <<>>;
        [] -> <<>>;
        Value -> unicode:characters_to_binary(Value)
    end.

telemetry_query(Req) ->
    Qs = cowboy_req:parse_qs(Req),
    Cursor = parse_int(proplists:get_value(<<"cursor">>, Qs, <<"0">>), 0),
    Limit = parse_int(proplists:get_value(<<"limit">>, Qs, <<"500">>), 500),
    {Cursor, Limit}.

parse_int(Value, Default) when is_binary(Value) ->
    case string:to_integer(binary_to_list(Value)) of
        {Int, _} when Int >= 0 -> Int;
        _ -> Default
    end;
parse_int(_, Default) ->
    Default.

read_policy_payload(Req0) ->
    case cowboy_req:read_body(Req0) of
        {ok, Body, Req1} ->
            try jsx:decode(Body, [return_maps]) of
                Payload ->
                    case maps:get(<<"sni">>, Payload, undefined) of
                        Sni when is_binary(Sni) -> {ok, normalize_sni(Sni), Req1};
                        _ -> {error, <<"missing_sni">>, Req1}
                    end
            catch
                _:_ -> {error, <<"invalid_json">>, Req1}
            end;
        {more, _Partial, Req1} ->
            {error, <<"body_too_large">>, Req1}
    end.

normalize_sni(Sni) ->
    Lower = string:lowercase(binary_to_list(Sni)),
    unicode:characters_to_binary(string:trim(Lower, trailing, ".")).

valid_sni(Sni) ->
    BaseDomain = kpproton_runtime:base_domain(),
    Suffix = <<".", BaseDomain/binary>>,
    ends_with(Sni, Suffix) andalso valid_dns_name(Sni).

ends_with(Bin, Suffix) when byte_size(Bin) >= byte_size(Suffix) ->
    Size = byte_size(Suffix),
    binary:part(Bin, byte_size(Bin) - Size, Size) =:= Suffix;
ends_with(_, _) ->
    false.

valid_dns_name(Sni) ->
    Labels = binary:split(Sni, <<".">>, [global]),
    Labels =/= [] andalso lists:all(fun valid_dns_label/1, Labels).

valid_dns_label(Label) when byte_size(Label) >= 1, byte_size(Label) =< 63 ->
    re:run(Label, <<"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$">>, [{capture, none}]) =:= match;
valid_dns_label(_) ->
    false.
%% END_BLOCK_VALIDATE_REQUEST

%% START_BLOCK_SAFE_RESPONSE
reply_json(Status, Body, Req0, State) ->
    Req = cowboy_req:reply(
        Status,
        #{<<"content-type">> => <<"application/json; charset=utf-8">>},
        jsx:encode(Body),
        Req0
    ),
    {ok, Req, State}.

mask_sni(Sni) ->
    case binary:split(Sni, <<".">>) of
        [Label, Rest] when byte_size(Label) > 4 ->
            <<(binary:part(Label, 0, 4))/binary, "...", Rest/binary>>;
        _ ->
            <<"redacted">>
    end.
%% END_BLOCK_SAFE_RESPONSE
