-module(kpproton_mtproto_boot).
-behaviour(gen_server).

%% FILE: src/kpproton_mtproto_boot.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Keep mtproto_proxy startup resilient by retrying boot until upstream connectivity is available.
%%   SCOPE: Start mtproto_proxy asynchronously, seed the base domain policy table, and keep the portal alive during degraded proxy startup.
%%   DEPENDS: M-CONFIG, M-PROXY-BRIDGE
%%   LINKS: M-CONFIG, M-PROXY-BRIDGE, M-RELEASE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start_link/0 - starts the mtproto boot manager
%%   handle_info/2 - retries mtproto_proxy startup until it succeeds
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added retrying mtproto_proxy boot manager to avoid crashing the whole release on transient upstream failures.
%% END_CHANGE_SUMMARY

-export([start_link/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

init([]) ->
    self() ! ensure_mtproto_started,
    {ok, #{booted => false}}.

handle_call(_Msg, _From, State) ->
    {reply, ok, State}.

handle_cast(_Msg, State) ->
    {noreply, State}.

%% START_BLOCK_RETRY_BOOT
handle_info(ensure_mtproto_started, #{booted := true} = State) ->
    {noreply, State};
handle_info(ensure_mtproto_started, State) ->
    io:format("[M-CONFIG][load][READ_ENV]~n", []),
    case application:ensure_all_started(mtproto_proxy) of
        {ok, _Started} ->
            case kpproton_app:seed_base_domain() of
                ok ->
                    io:format("[M-CONFIG][validate][VALIDATE_REQUIRED]~n", []),
                    io:format("[M-CONFIG][render][EMIT_RUNTIME]~n", []),
                    {noreply, State#{booted => true}};
                {error, Reason} ->
                    schedule_retry(Reason),
                    {noreply, State}
            end;
        {error, Reason} ->
            schedule_retry(Reason),
            {noreply, State}
    end;
handle_info(_Info, State) ->
    {noreply, State}.
%% END_BLOCK_RETRY_BOOT

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

schedule_retry(Reason) ->
    io:format("[M-CONFIG][render][EMIT_RUNTIME] mtproto boot deferred: ~p~n", [Reason]),
    erlang:send_after(kpproton_app:mtproxy_boot_retry_ms(), self(), ensure_mtproto_started).
