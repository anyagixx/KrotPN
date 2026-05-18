-module(kpproton_proxy_issue).

%% FILE: apps/kpproton_proxy/src/provisioning/kpproton_proxy_issue.erl
%% VERSION: 1.3.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Define the issuance contract that turns a verified email into a stable SNI domain and tg://proxy link.
%%   SCOPE: Deterministic SNI generation, idempotent assignment reuse, proxy link assembly, and policy action contract output.
%%   DEPENDS: M-REGISTRY, M-PROXY-BRIDGE
%%   LINKS: M-PROXY-ISSUE, M-WEB-API
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   generate_sni/2 - creates a hex-prefixed subdomain for a verified email
%%   build_tg_link/5 - assembles the tg://proxy link with a derived per-SNI secret
%%   issue_proxy_for_email/6 - returns idempotent assignment metadata and policy action info
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.3.0 - Replaced raw-base-secret links with derived per-SNI fake-TLS credentials and rebuild reused assignments with the same canonical derivation.
%% END_CHANGE_SUMMARY

-export([generate_sni/2, build_tg_link/5, issue_proxy_for_email/6]).

%% START_BLOCK_GENERATE_SNI
generate_sni(Email, BaseDomain) ->
    io:format("[M-PROXY-ISSUE][issue_proxy_for_email][GENERATE_SNI]~n", []),
    HashHex = binary:encode_hex(crypto:hash(sha256, Email)),
    Prefix = binary:part(HashHex, 0, 12),
    <<Prefix/binary, ".", BaseDomain/binary>>.
%% END_BLOCK_GENERATE_SNI

%% START_BLOCK_BUILD_TG_LINK
build_tg_link(Host, SecretHex, SecretSalt, Port, SniDomain) ->
    io:format("[M-PROXY-ISSUE][issue_proxy_for_email][BUILD_TG_LINK]~n", []),
    BaseSecret = binary:decode_hex(SecretHex),
    DerivedSecret = mtp_fake_tls:derive_sni_secret(BaseSecret, SniDomain, SecretSalt),
    FakeTlsSecret = mtp_fake_tls:format_secret_hex(DerivedSecret, SniDomain),
    iolist_to_binary([
        <<"tg://proxy?server=">>, Host,
        <<"&port=">>, integer_to_binary(Port),
        <<"&secret=">>, FakeTlsSecret
    ]).
%% END_BLOCK_BUILD_TG_LINK

%% START_BLOCK_PERSIST_ASSIGNMENT
issue_proxy_for_email(Email, BaseDomain, SecretHex, SecretSalt, ExistingAssignment, Port) ->
    case ExistingAssignment of
        #{sni := ExistingSni} = Assignment ->
            io:format("[M-PROXY-ISSUE][issue_proxy_for_email][PERSIST_ASSIGNMENT]~n", []),
            Assignment#{
                tg_link => build_tg_link(ExistingSni, SecretHex, SecretSalt, Port, ExistingSni),
                credential_mode => derived_per_sni,
                policy_action => reuse
            };
        undefined ->
            SniDomain = generate_sni(Email, BaseDomain),
            TgLink = build_tg_link(SniDomain, SecretHex, SecretSalt, Port, SniDomain),
            io:format("[M-PROXY-ISSUE][issue_proxy_for_email][PERSIST_ASSIGNMENT]~n", []),
            #{
                email => Email,
                sni => SniDomain,
                tg_link => TgLink,
                credential_mode => derived_per_sni,
                policy_action => apply_domain_policy
            }
    end.
%% END_BLOCK_PERSIST_ASSIGNMENT
