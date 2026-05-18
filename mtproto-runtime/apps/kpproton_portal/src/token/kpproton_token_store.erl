-module(kpproton_token_store).

%% FILE: apps/kpproton_portal/src/token/kpproton_token_store.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Provide a one-time token lifecycle contract for the email verification flow.
%%   SCOPE: Create token records, atomically consume them, and purge expired entries from in-memory state.
%%   DEPENDS: M-CONFIG
%%   LINKS: M-TOKEN, M-WEB-API
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   create_token/3 - inserts a token with expiration metadata
%%   consume_token/3 - validates expiration and removes a token
%%   purge_expired/2 - clears stale tokens from a token map
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added foundational one-time token store contract.
%% END_CHANGE_SUMMARY

-export([create_token/3, consume_token/3, purge_expired/2]).

%% START_BLOCK_CREATE
create_token(Email, TtlSeconds, NowSeconds) when is_binary(Email), TtlSeconds > 0 ->
    Token = binary:encode_hex(crypto:strong_rand_bytes(16)),
    ExpiresAt = NowSeconds + TtlSeconds,
    io:format("[M-TOKEN][create][STORE_TOKEN]~n", []),
    {Token, #{email => Email, expires_at => ExpiresAt}};
create_token(_, _, _) ->
    erlang:error(badarg).
%% END_BLOCK_CREATE

%% START_BLOCK_CONSUME
consume_token(Token, TokenMap, NowSeconds) ->
    case maps:get(Token, TokenMap, undefined) of
        undefined ->
            {error, missing};
        #{expires_at := ExpiresAt} when ExpiresAt < NowSeconds ->
            io:format("[M-TOKEN][expire][PURGE_EXPIRED]~n", []),
            {error, expired};
        Record ->
            io:format("[M-TOKEN][consume][DELETE_TOKEN]~n", []),
            {ok, Record, maps:remove(Token, TokenMap)}
    end.
%% END_BLOCK_CONSUME

%% START_BLOCK_EXPIRE
purge_expired(TokenMap, NowSeconds) ->
    io:format("[M-TOKEN][expire][PURGE_EXPIRED]~n", []),
    maps:filter(
      fun(_Token, #{expires_at := ExpiresAt}) ->
              ExpiresAt >= NowSeconds
      end,
      TokenMap).
%% END_BLOCK_EXPIRE
