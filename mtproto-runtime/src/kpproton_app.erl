%% FILE: src/kpproton_app.erl
%% VERSION: 1.2.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Start the unified KPprotoN OTP application and configure upstream runtime integrations before supervision begins.
%%   SCOPE: Read env-backed release settings, inject `mtproto_proxy` application config, seed the base domain, and start the top-level supervisor.
%%   DEPENDS: M-CONFIG, M-RELEASE, M-PROXY-BRIDGE
%%   LINKS: M-CONFIG, M-RELEASE, M-PROXY-BRIDGE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start/2 - configures the runtime and starts the supervisor tree
%%   stop/1 - stops the OTP application
%%   seed_base_domain/0 - inserts the apex domain into the MTProto policy table
%%   mtproxy_boot_retry_ms/0 - returns the mtproto boot retry interval
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.2.0 - Enable per-SNI secret enforcement so the MTProto listener rejects raw-base-secret fake-TLS handshakes.
%% END_CHANGE_SUMMARY

-module(kpproton_app).
-behaviour(application).

-export([start/2, stop/1, seed_base_domain/0, mtproxy_boot_retry_ms/0]).

env_string(Key, Default) ->
    case os:getenv(Key) of
        false -> Default;
        Value -> Value
    end.

env_binary(Key, Default) ->
    unicode:characters_to_binary(env_string(Key, binary_to_list(Default))).

env_integer(Key, Default) ->
    case string:to_integer(env_string(Key, integer_to_list(Default))) of
        {Int, _} -> Int;
        _ -> Default
    end.

configure_mtproto_proxy() ->
    Secret = env_binary("PROXY_SECRET_HEX", <<"0123456789abcdef0123456789abcdef">>),
    SecretSalt = kpproton_runtime:proxy_secret_salt(),
    Tag = env_binary("PROXY_AD_TAG", <<>>),
    Port = env_integer("PROXY_PORT", 443),
    DomainFronting = env_string("PORTAL_DOMAIN_FRONTING", "127.0.0.1:8443"),
    PortalPort = env_integer("PORTAL_HTTP_INTERNAL_PORT", 8080),
    LocalBootstrapBase = "http://127.0.0.1:" ++ integer_to_list(PortalPort) ++ "/bootstrap",
    application:load(mtproto_proxy),
    ok = application:set_env(mtproto_proxy, listen_ip, env_string("PROXY_LISTEN_IP", "0.0.0.0")),
    ok = application:set_env(mtproto_proxy, ports, [
        #{
            name => kpproton_proxy_listener,
            port => Port,
            secret => Secret,
            tag => Tag
        }
    ]),
    ok = application:set_env(mtproto_proxy, allowed_protocols, [mtp_fake_tls]),
    ok = application:set_env(mtproto_proxy, domain_fronting, DomainFronting),
    ok = application:set_env(mtproto_proxy, domain_fronting_timeout_sec, env_integer("DOMAIN_FRONTING_TIMEOUT_SEC", 10)),
    ok = application:set_env(mtproto_proxy, core_api_http_timeout_ms, env_integer("CORE_API_HTTP_TIMEOUT_MS", 10000)),
    ok = application:set_env(mtproto_proxy, proxy_secret_url, LocalBootstrapBase ++ "/proxy-secret"),
    ok = application:set_env(mtproto_proxy, proxy_config_url, LocalBootstrapBase ++ "/proxy-config"),
    ok = application:set_env(mtproto_proxy, per_sni_secret_salt, SecretSalt),
    ok = application:set_env(mtproto_proxy, policy, [
        {in_table, tls_domain, personal_domains},
        {max_connections, [tls_domain], env_integer("MAX_CONNECTIONS_PER_DOMAIN", 100)}
    ]),
    ok = application:set_env(mtproto_proxy, per_sni_secrets, on).

seed_base_domain() ->
    case whereis(mtp_policy_table) of
        undefined ->
            {error, mtproto_policy_table_unavailable};
        _Pid ->
            ok = mtp_policy_table:add(personal_domains, tls_domain, kpproton_runtime:base_domain()),
            ok
    end.

mtproxy_boot_retry_ms() ->
    env_integer("MTPROXY_BOOT_RETRY_SECONDS", 15) * 1000.

start(_StartType, _StartArgs) ->
    application:ensure_all_started(inets),
    configure_mtproto_proxy(),
    kpproton_sup:start_link().

stop(_State) ->
    ok.
