-module(kpproton_registry).

%% FILE: apps/kpproton_proxy/src/registry/kpproton_registry.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Define the DETS-backed persistence contract for issued proxy assignments.
%%   SCOPE: Open registry file, lookup users by email, and save deterministic assignment records.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-REGISTRY, M-PROXY-ISSUE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   open_registry/1 - opens a DETS table at the configured path
%%   lookup_user/2 - reads an existing assignment by email
%%   save_user/3 - writes or replaces an assignment record keyed by email
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added DETS registry contract for user assignment persistence.
%% END_CHANGE_SUMMARY

-export([open_registry/1, lookup_user/2, save_user/3, close_registry/1]).

%% START_BLOCK_OPEN_DETS
open_registry(Path) ->
    io:format("[M-REGISTRY][open][OPEN_DETS]~n", []),
    ok = filelib:ensure_dir(Path),
    dets:open_file(kpproton_registry, [{file, Path}, {type, set}]).
%% END_BLOCK_OPEN_DETS

%% START_BLOCK_LOOKUP_EMAIL
lookup_user(Email, Table) ->
    io:format("[M-REGISTRY][lookup_user][LOOKUP_EMAIL]~n", []),
    case dets:lookup(Table, Email) of
        [{Email, Assignment}] -> Assignment;
        [] -> undefined
    end.
%% END_BLOCK_LOOKUP_EMAIL

%% START_BLOCK_WRITE_ASSIGNMENT
save_user(Email, Assignment, Table) ->
    io:format("[M-REGISTRY][save_user][WRITE_ASSIGNMENT]~n", []),
    ok = dets:insert(Table, {Email, Assignment}),
    ok.
%% END_BLOCK_WRITE_ASSIGNMENT

close_registry(Table) ->
    dets:close(Table).
