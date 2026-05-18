-module(kpproton_bootstrap_secret_handler).
-behaviour(cowboy_handler).

%% FILE: apps/kpproton_portal/src/http/kpproton_bootstrap_secret_handler.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Expose the Telegram bootstrap secret to the local mtproto_proxy bootstrap path.
%%   SCOPE: Fetch proxy secret via kpproton_core_api and normalize handler failures into stable HTTP responses.
%%   DEPENDS: M-RELEASE
%%   LINKS: M-WEB-API, M-PROXY-BRIDGE, M-RELEASE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   init/2 - returns the local bootstrap secret payload or a 502 fallback
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added MyGRACE source contract metadata for the bootstrap secret handler.
%% END_CHANGE_SUMMARY

-export([init/2]).

%% START_BLOCK_INIT
init(Req0, State) ->
    {Status, Body} =
        case kpproton_core_api:proxy_secret() of
            {ok, Secret} -> {200, Secret};
            {error, _} -> {502, <<"bootstrap secret unavailable">>}
        end,
    Req = cowboy_req:reply(Status, #{<<"content-type">> => <<"text/plain; charset=utf-8">>}, Body, Req0),
    {ok, Req, State}.
%% END_BLOCK_INIT
