-module(kpproton_sup).
-behaviour(supervisor).

%% FILE: src/kpproton_sup.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Supervise the runtime, web, and MTProto boot workers for the unified application.
%%   SCOPE: Start the top-level supervisor tree and define child restart semantics.
%%   DEPENDS: M-RELEASE
%%   LINKS: M-RELEASE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start_link/0 - starts the top-level supervisor
%%   init/1 - returns the child spec tree
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added MyGRACE source contract metadata for the top-level supervisor.
%% END_CHANGE_SUMMARY

-export([start_link/0]).
-export([init/1]).

%% START_BLOCK_START_LINK
start_link() ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, []).
%% END_BLOCK_START_LINK

%% START_BLOCK_INIT
init([]) ->
    RuntimeChild = #{
        id => kpproton_runtime,
        start => {kpproton_runtime, start_link, []},
        restart => permanent,
        shutdown => 5000,
        type => worker,
        modules => [kpproton_runtime]
    },
    WebChild = #{
        id => kpproton_web,
        start => {kpproton_web, start_link, []},
        restart => permanent,
        shutdown => 5000,
        type => worker,
        modules => [kpproton_web]
    },
    MtprotoBootChild = #{
        id => kpproton_mtproto_boot,
        start => {kpproton_mtproto_boot, start_link, []},
        restart => permanent,
        shutdown => 5000,
        type => worker,
        modules => [kpproton_mtproto_boot]
    },
    {ok, {{one_for_one, 5, 10}, [RuntimeChild, WebChild, MtprotoBootChild]}}.
%% END_BLOCK_INIT
