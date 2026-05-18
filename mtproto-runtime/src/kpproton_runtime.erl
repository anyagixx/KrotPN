%% FILE: src/kpproton_runtime.erl
%% VERSION: 1.1.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Expose canonical runtime configuration and token state to portal and proxy modules.
%%   SCOPE: Read env-backed settings, store verification tokens, and provide shared getters for release-time components.
%%   DEPENDS: M-CONFIG, M-TOKEN, M-RELEASE
%%   LINKS: M-CONFIG, M-TOKEN, M-RELEASE, M-PROXY-ISSUE
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start_link/0 - starts the runtime token process
%%   create_token/1 - creates and stores a verification token
%%   consume_token/1 - consumes a stored verification token
%%   base_domain/0 - returns the configured base domain
%%   proxy_secret/0 - returns the base MTProto secret
%%   proxy_secret_salt/0 - returns the private per-SNI derivation salt
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.1.0 - Added a required per-SNI salt runtime getter for MTProto credential hardening.
%% END_CHANGE_SUMMARY

-module(kpproton_runtime).
-behaviour(gen_server).

-export([start_link/0]).
-export([
    create_token/1,
    consume_token/1,
    base_domain/0,
    proxy_secret/0,
    proxy_secret_salt/0,
    proxy_port/0,
    token_ttl/0,
    resend_api_key/0,
    resend_from/0,
    registry_path/0,
    static_root/0,
    portal_port/0,
    portal_tls_port/0,
    tls_cert_path/0,
    tls_key_path/0
]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-define(TOKEN_TABLE, kpproton_tokens).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

create_token(Email) ->
    gen_server:call(?MODULE, {create_token, Email}).

consume_token(Token) ->
    gen_server:call(?MODULE, {consume_token, Token}).

base_domain() ->
    env_binary("BASE_DOMAIN", <<"example.com">>).

proxy_secret() ->
    env_binary("PROXY_SECRET_HEX", <<"0123456789abcdef0123456789abcdef">>).

proxy_secret_salt() ->
    required_env_binary("PROXY_SECRET_SALT").

proxy_port() ->
    env_integer("PROXY_PORT", 443).

token_ttl() ->
    env_integer("TOKEN_TTL_SECONDS", 1800).

resend_api_key() ->
    env_binary("RESEND_API_KEY", <<>>).

resend_from() ->
    env_binary("RESEND_FROM", <<"KPprotoN <noreply@example.com>">>).

registry_path() ->
    env_string("DETS_DATA_DIR", "/var/lib/kpproton/dets") ++ "/registry.dets".

static_root() ->
    env_string("KP_STATIC_DIR", filename:absname("apps/kpproton_portal/priv/static")).

portal_port() ->
    env_integer("PORTAL_HTTP_INTERNAL_PORT", 8080).

portal_tls_port() ->
    env_integer("PORTAL_TLS_INTERNAL_PORT", 8443).

tls_cert_path() ->
    env_string("TLS_CERT_PATH", "/certs/live/example.com/fullchain.pem").

tls_key_path() ->
    env_string("TLS_KEY_PATH", "/certs/live/example.com/privkey.pem").

init([]) ->
    _ = ets:new(?TOKEN_TABLE, [named_table, public, set]),
    {ok, #{}}.

handle_call({create_token, Email}, _From, State) ->
    Now = erlang:system_time(second),
    {Token, Record} = kpproton_token_store:create_token(Email, token_ttl(), Now),
    true = ets:insert(?TOKEN_TABLE, {Token, Record}),
    {reply, {ok, Token, Record}, State};
handle_call({consume_token, Token}, _From, State) ->
    Now = erlang:system_time(second),
    Reply =
        case ets:lookup(?TOKEN_TABLE, Token) of
            [] ->
                {error, missing};
            [{Token, Record}] ->
                case kpproton_token_store:consume_token(Token, #{Token => Record}, Now) of
                    {ok, Consumed, _} ->
                        true = ets:delete(?TOKEN_TABLE, Token),
                        {ok, Consumed};
                    {error, expired} ->
                        true = ets:delete(?TOKEN_TABLE, Token),
                        {error, expired};
                    Error ->
                        Error
                end
        end,
    {reply, Reply, State};
handle_call(_Msg, _From, State) ->
    {reply, {error, unsupported}, State}.

handle_cast(_Msg, State) ->
    {noreply, State}.

handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

env_string(Key, Default) ->
    case os:getenv(Key) of
        false -> Default;
        Value -> Value
    end.

env_binary(Key, Default) ->
    unicode:characters_to_binary(env_string(Key, binary_to_list(Default))).

required_env_binary(Key) ->
    unicode:characters_to_binary(required_env_string(Key)).

env_integer(Key, Default) ->
    case string:to_integer(env_string(Key, integer_to_list(Default))) of
        {Int, _} -> Int;
        _ -> Default
    end.

required_env_string(Key) ->
    case os:getenv(Key) of
        false -> erlang:error({missing_env, Key});
        [] -> erlang:error({empty_env, Key});
        Value -> Value
    end.
