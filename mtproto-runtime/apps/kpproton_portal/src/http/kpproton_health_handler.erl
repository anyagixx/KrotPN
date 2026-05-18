-module(kpproton_health_handler).
-behaviour(cowboy_handler).

%% FILE: apps/kpproton_portal/src/http/kpproton_health_handler.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Expose a lightweight JSON health endpoint for probes and operator smoke checks.
%%   SCOPE: Serialize the shared request-handler health payload and return it as HTTP 200 JSON.
%%   DEPENDS: M-WEB-API
%%   LINKS: M-WEB-API
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   init/2 - returns the health payload as a JSON Cowboy response
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added MyGRACE source contract metadata for the health endpoint handler.
%% END_CHANGE_SUMMARY

-export([init/2]).

%% START_BLOCK_INIT
init(Req0, State) ->
    Body = jsx:encode(kpproton_request_handler:health_response()),
    Req = cowboy_req:reply(200, #{<<"content-type">> => <<"application/json">>}, Body, Req0),
    {ok, Req, State}.
%% END_BLOCK_INIT
