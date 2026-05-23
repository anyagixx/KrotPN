-module(kpproton_proxy_bridge).

%% FILE: apps/kpproton_proxy/src/mtproto/kpproton_proxy_bridge.erl
%% VERSION: 1.3.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Provide the runtime bridge contract that applies a newly issued SNI policy into the MTProto edge layer.
%%   SCOPE: Observable policy apply/revoke hooks and health state used by KrotPN runtime policy sync.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-PROXY-BRIDGE, M-PROXY-ISSUE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   apply_domain_policy/1 - loads the issued SNI into mtproto_proxy policy state
%%   revoke_domain_policy/1 - removes an issued SNI from mtproto_proxy policy state
%%   health/0 - returns safe policy table health metadata
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.3.0 - Make policy apply idempotent by replacing an existing SNI entry before add.
%%   LAST_CHANGE: v1.2.0 - Added KrotPN HTTP policy bridge support for apply, revoke, and health.
%%   LAST_CHANGE: v1.1.0 - Replaced log-only bridge with live mtp_policy_table integration.
%% END_CHANGE_SUMMARY

-export([apply_domain_policy/1, revoke_domain_policy/1, health/0]).

%% START_BLOCK_APPLY_POLICY
apply_domain_policy(SniDomain) ->
    io:format("[M-PROXY-BRIDGE][apply_domain_policy][LOAD_POLICY]~n", []),
    case whereis(mtp_policy_table) of
        undefined ->
            {error, mtproto_policy_table_unavailable};
        _Pid ->
            _ = catch mtp_policy_table:del(personal_domains, tls_domain, SniDomain),
            ok = mtp_policy_table:add(personal_domains, tls_domain, SniDomain),
            io:format("[M-PROXY-BRIDGE][apply_domain_policy][APPLY_POLICY] ~ts~n", [SniDomain]),
            ok
    end.
%% END_BLOCK_APPLY_POLICY

%% START_BLOCK_REVOKE_POLICY
revoke_domain_policy(SniDomain) ->
    io:format("[M-PROXY-BRIDGE][revoke_domain_policy][LOAD_POLICY]~n", []),
    case whereis(mtp_policy_table) of
        undefined ->
            {error, mtproto_policy_table_unavailable};
        _Pid ->
            ok = mtp_policy_table:del(personal_domains, tls_domain, SniDomain),
            io:format("[M-PROXY-BRIDGE][revoke_domain_policy][REVOKE_POLICY] ~ts~n", [SniDomain]),
            ok
    end.
%% END_BLOCK_REVOKE_POLICY

%% START_BLOCK_BRIDGE_HEALTH
health() ->
    case whereis(mtp_policy_table) of
        undefined ->
            #{status => <<"degraded">>, failure_code => <<"policy_table_unavailable">>};
        _Pid ->
            #{
                status => <<"healthy">>,
                adapter_name => <<"kpproton-mtproto-proxy">>,
                policy_count => mtp_policy_table:table_size(personal_domains)
            }
    end.
%% END_BLOCK_BRIDGE_HEALTH
