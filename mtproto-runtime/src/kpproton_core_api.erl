-module(kpproton_core_api).

%% FILE: src/kpproton_core_api.erl
%% VERSION: 1.3.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Fetch Telegram core bootstrap artifacts through the system curl binary with bounded local fallbacks for mtproto_proxy startup.
%%   SCOPE: Retrieve getProxySecret/getProxyConfig payloads, filter unreachable downstreams, require a complete common Telegram DC downstream set, provide static fallback artifacts, and normalize failures for local bootstrap handlers.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-PROXY-BRIDGE, M-RELEASE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   proxy_secret/0 - returns the getProxySecret payload as binary
%%   proxy_config/0 - returns the getProxyConfig payload as binary
%%   has_required_downstreams/1 - validates that bootstrap config contains common Telegram DC pools
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.3.0 - Require common Telegram DC downstreams and expand static fallback config to prevent no_pool crashes after reboot.
%%   LAST_CHANGE: v1.2.0 - Added bounded static fallback bootstrap artifacts so mtproto_proxy can start when core.telegram.org is slow or blocked.
%%   LAST_CHANGE: v1.1.0 - Filter unreachable bootstrap downstreams before exposing proxy config to mtproto_proxy.
%% END_CHANGE_SUMMARY

-export([proxy_secret/0, proxy_config/0]).

%% START_BLOCK_FETCH_CORE_API
proxy_secret() ->
    case fetch_url(os:getenv("PROXY_SECRET_URL", "https://core.telegram.org/getProxySecret")) of
        {ok, Body} ->
            {ok, Body};
        {error, Reason} ->
            io:format("[M-PROXY-BRIDGE][bootstrap][STATIC_SECRET_FALLBACK] reason=~p~n", [safe_reason(Reason)]),
            {ok, fallback_proxy_secret()}
    end.

proxy_config() ->
    case fetch_url(os:getenv("PROXY_CONFIG_URL", "https://core.telegram.org/getProxyConfig")) of
        {ok, Body} ->
            Filtered = filter_proxy_config(Body),
            case has_required_downstreams(Filtered) of
                true ->
                    {ok, Filtered};
                false ->
                    io:format("[M-PROXY-BRIDGE][bootstrap][STATIC_CONFIG_FALLBACK] reason=missing_required_downstreams~n", []),
                    {ok, fallback_proxy_config()}
            end;
        Error ->
            io:format("[M-PROXY-BRIDGE][bootstrap][STATIC_CONFIG_FALLBACK] reason=~p~n", [safe_reason(Error)]),
            {ok, fallback_proxy_config()}
    end.

fetch_url(Url) ->
    TimeoutSeconds = env_integer("BOOTSTRAP_CORE_FETCH_TIMEOUT_SECONDS", 3),
    Port = open_port(
        {spawn_executable, "/usr/bin/curl"},
        [
            binary,
            exit_status,
            use_stdio,
            stderr_to_stdout,
            {args, ["-fsSL", "--max-time", integer_to_list(TimeoutSeconds), Url]}
        ]
    ),
    collect_output(Port, <<>>, TimeoutSeconds).

collect_output(Port, Acc, TimeoutSeconds) ->
    receive
        {Port, {data, Data}} ->
            collect_output(Port, <<Acc/binary, Data/binary>>, TimeoutSeconds);
        {Port, {exit_status, 0}} ->
            {ok, Acc};
        {Port, {exit_status, Status}} ->
            {error, {curl_failed, Status, Acc}}
    after (TimeoutSeconds + 2) * 1000 ->
        port_close(Port),
        {error, timeout}
    end.

filter_proxy_config(Body) ->
    TimeoutMs = env_integer("BOOTSTRAP_DOWNSTREAM_CONNECT_TIMEOUT_MS", 1000),
    Lines = binary:split(Body, <<"\n">>, [global]),
    Filtered =
        lists:reverse(
          lists:foldl(
            fun(Line, Acc) ->
                case should_keep_line(Line, TimeoutMs) of
                    true -> [Line | Acc];
                    false -> Acc
                end
            end,
            [],
            Lines
          )
        ),
    iolist_to_binary(lists:join(<<"\n">>, Filtered)).

should_keep_line(<<>>, _TimeoutMs) ->
    true;
should_keep_line(<<"proxy_for ", _/binary>> = Line, TimeoutMs) ->
    case parse_downstream_line(Line) of
        {ok, DcId, Host, Port} ->
            case downstream_reachable(Host, Port, TimeoutMs) of
                true ->
                    true;
                false ->
                    io:format(
                      "[M-PROXY-BRIDGE][apply_domain_policy][LOAD_POLICY] filtered unreachable downstream dc=~p host=~s port=~p~n",
                      [DcId, binary_to_list(Host), Port]
                    ),
                    false
            end;
        error ->
            true
    end;
should_keep_line(_Line, _TimeoutMs) ->
    true.

has_required_downstreams(Body) ->
    lists:all(
      fun(DcId) ->
          has_downstream(Body, DcId)
      end,
      [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 203, -203]
    ).

has_downstream(Body, DcId) ->
    Marker = iolist_to_binary(["proxy_for ", integer_to_list(DcId), " "]),
    binary:match(Body, Marker) =/= nomatch.

fallback_proxy_secret() ->
    decode_base64_env(
      "PROXY_SECRET_B64",
      <<"xPn6ypZ45rtIrWx+LOXA0kQwZF1VSt3rVUGeA02mJyHQRuqrblKrFKlaRD7Ps0Y+eaBaZmEq35yu2ovpqA2mmG+wpv84evhNiO86ZBNxPlwzd/bho9R9mfXgxW7s6PBcVMSQsHnjG++C/w7o8rCjJ1bSScXyEmmBbLcGGyZdshI=">>
    ).

fallback_proxy_config() ->
    case os:getenv("PROXY_CONFIG_B64") of
        false ->
            fallback_proxy_config_default();
        [] ->
            fallback_proxy_config_default();
        Value ->
            base64:decode(unicode:characters_to_binary(Value))
    end.

fallback_proxy_config_default() ->
    <<"# force_probability 10 10\n",
      "default 2;\n",
      "proxy_for 1 149.154.175.50:8888;\n",
      "proxy_for -1 149.154.175.50:8888;\n",
      "proxy_for 2 149.154.161.144:8888;\n",
      "proxy_for -2 149.154.161.184:8888;\n",
      "proxy_for 203 91.105.192.110:443;\n",
      "proxy_for -203 91.105.192.110:443;\n",
      "proxy_for 3 149.154.175.100:8888;\n",
      "proxy_for -3 149.154.175.100:8888;\n",
      "proxy_for 4 91.108.4.209:8888;\n",
      "proxy_for 4 91.108.4.154:8888;\n",
      "proxy_for 4 91.108.4.172:8888;\n",
      "proxy_for 4 91.108.4.227:8888;\n",
      "proxy_for 4 91.108.4.149:8888;\n",
      "proxy_for 4 91.108.4.163:8888;\n",
      "proxy_for 4 91.108.4.215:8888;\n",
      "proxy_for 4 91.108.4.196:8888;\n",
      "proxy_for 4 91.108.4.140:8888;\n",
      "proxy_for 4 91.108.4.169:8888;\n",
      "proxy_for -4 149.154.165.250:8888;\n",
      "proxy_for -4 149.154.164.250:8888;\n",
      "proxy_for 5 91.108.56.187:8888;\n",
      "proxy_for 5 91.108.56.147:8888;\n",
      "proxy_for -5 91.108.56.187:8888;\n",
      "proxy_for -5 91.108.56.147:8888;\n">>.

decode_base64_env(Key, Default) ->
    Encoded =
        case os:getenv(Key) of
            false -> Default;
            [] -> Default;
            Value -> unicode:characters_to_binary(Value)
        end,
    base64:decode(Encoded).

safe_reason({curl_failed, Status, _Body}) ->
    {curl_failed, Status};
safe_reason({error, Reason}) ->
    safe_reason(Reason);
safe_reason(Reason) ->
    Reason.

parse_downstream_line(Line) ->
    try
        [<<"proxy_for">>, DcIdBin, HostPort0] = binary:split(Line, <<" ">>, [global]),
        HostPort =
            case binary:last(HostPort0) of
                $; ->
                    binary:part(HostPort0, 0, byte_size(HostPort0) - 1);
                _ ->
                    HostPort0
            end,
        [Host, PortBin] = binary:split(HostPort, <<":">>),
        {ok, binary_to_integer(DcIdBin), Host, binary_to_integer(PortBin)}
    catch
        _:_ ->
            error
    end.

downstream_reachable(Host, Port, TimeoutMs) ->
    case gen_tcp:connect(binary_to_list(Host), Port, [binary, {packet, raw}, {active, false}], TimeoutMs) of
        {ok, Socket} ->
            ok = gen_tcp:close(Socket),
            true;
        {error, _Reason} ->
            false
    end.

env_integer(Key, Default) ->
    case os:getenv(Key) of
        false ->
            Default;
        Value ->
            case string:to_integer(Value) of
                {Int, _} -> Int;
                _ -> Default
            end
    end.
%% END_BLOCK_FETCH_CORE_API
