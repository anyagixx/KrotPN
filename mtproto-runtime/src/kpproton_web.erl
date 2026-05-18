-module(kpproton_web).
-behaviour(gen_server).

%% FILE: src/kpproton_web.erl
%% VERSION: 1.2.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Start Cowboy HTTP and HTTPS listeners that expose bootstrap, policy bridge, and health routes.
%%   SCOPE: Build the dispatch table, open private-bind policy/portal listeners, and stop them cleanly on termination.
%%   DEPENDS: M-RELEASE
%%   LINKS: M-RELEASE, M-WEB-API, M-WEB-UI
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start_link/0 - starts the web runtime server
%%   init/1 - boots Cowboy listeners and dispatch rules using POLICY_LISTEN_IP
%%   terminate/2 - stops Cowboy listeners during shutdown
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.2.0 - Bind policy/portal listeners to POLICY_LISTEN_IP for Phase-38 DE runtime privacy.
%%   LAST_CHANGE: v1.1.0 - Added KrotPN token-protected MTProto policy bridge routes.
%%   LAST_CHANGE: v1.0.0 - Added MyGRACE source contract metadata for the Cowboy web runtime.
%% END_CHANGE_SUMMARY

-export([start_link/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

%% START_BLOCK_START_LINK
start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).
%% END_BLOCK_START_LINK

%% START_BLOCK_INIT
init([]) ->
    PolicyListenIp = kpproton_runtime:policy_listen_ip(),
    Dispatch = cowboy_router:compile([
        {'_', [
            {"/", cowboy_static, {file, filename:join(kpproton_runtime:static_root(), "index.html")}},
            {"/static/[...]", cowboy_static, {dir, kpproton_runtime:static_root()}},
            {"/bootstrap/proxy-secret", kpproton_bootstrap_secret_handler, #{}},
            {"/bootstrap/proxy-config", kpproton_bootstrap_config_handler, #{}},
            {"/krotpn/mtproto/policy/apply", kpproton_policy_handler, #{operation => apply}},
            {"/krotpn/mtproto/policy/revoke", kpproton_policy_handler, #{operation => revoke}},
            {"/krotpn/mtproto/policy/health", kpproton_policy_handler, #{operation => health}},
            {"/api/request", kpproton_request_handler, #{}},
            {"/verify", kpproton_verify_handler, #{}},
            {"/health", kpproton_health_handler, #{}}
        ]}
    ]),
    {ok, _} = cowboy:start_clear(
        kpproton_http,
        [{ip, PolicyListenIp}, {port, kpproton_runtime:portal_port()}],
        #{env => #{dispatch => Dispatch}}
    ),
    {ok, _} = cowboy:start_tls(
        kpproton_https,
        [
            {ip, PolicyListenIp},
            {port, kpproton_runtime:portal_tls_port()},
            {certfile, kpproton_runtime:tls_cert_path()},
            {keyfile, kpproton_runtime:tls_key_path()}
        ],
        #{env => #{dispatch => Dispatch}}
    ),
    {ok, #{}}.
%% END_BLOCK_INIT

%% START_BLOCK_GEN_SERVER_CALLBACKS
handle_call(_Msg, _From, State) ->
    {reply, ok, State}.

handle_cast(_Msg, State) ->
    {noreply, State}.

handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok = cowboy:stop_listener(kpproton_http),
    ok = cowboy:stop_listener(kpproton_https),
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.
%% END_BLOCK_GEN_SERVER_CALLBACKS
