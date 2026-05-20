-module(kpproton_usage_telemetry).

%% FILE: apps/kpproton_proxy/src/mtproto/kpproton_usage_telemetry.erl
%% VERSION: 1.2.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Keep bounded, secret-free MTProto runtime telemetry for KrotPN admin analytics.
%%   SCOPE: Safe event emission, mtproto_proxy metric counters, active-SNI sampling helpers, cursor-based drain, overflow accounting.
%%   DEPENDS: M-PROXY-BRIDGE, M-RELEASE
%%   LINKS: M-055
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   emit_event/1 - appends one secret-free runtime telemetry event to the bounded buffer
%%   add_metric/2 - records hot-path mtproto_proxy counters for sampler draining
%%   drain_metric_counters/0 - returns and clears accumulated runtime counters
%%   active_domain_counts/0 - reads current per-SNI active connection counters
%%   snapshot/0 - returns current telemetry counters without draining events
%%   drain/2 - returns cursor-ordered events and next cursor
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.2.0 - Added Phase-43 runtime CPU/RAM resource metrics to telemetry snapshots.
%%   LAST_CHANGE: v1.1.0 - Added metric counter drain and active-SNI snapshot helpers for live runtime telemetry.
%%   LAST_CHANGE: v1.0.0 - Added Phase-42 bounded telemetry buffer contract.
%% END_CHANGE_SUMMARY

-export([emit_event/1, add_metric/2, drain_metric_counters/0, active_domain_counts/0, snapshot/0, drain/2]).

-define(TABLE, kpproton_usage_telemetry).
-define(METRIC_TABLE, kpproton_usage_metric_counters).
-define(DROPPED_KEY, {kpproton_usage_telemetry, dropped_events}).
-define(MAX_BUFFER, 1000).

%% START_BLOCK_TABLE_HELPERS
ensure_table() ->
    case ets:info(?TABLE) of
        undefined ->
            try ets:new(?TABLE, [named_table, public, ordered_set]) of
                _ -> ok
            catch
                error:badarg -> ok
            end;
        _Info ->
            ok
    end.

ensure_metric_table() ->
    case ets:info(?METRIC_TABLE) of
        undefined ->
            try ets:new(?METRIC_TABLE, [named_table, public, set, {write_concurrency, true}]) of
                _ -> ok
            catch
                error:badarg -> ok
            end;
        _Info ->
            ok
    end.

next_cursor() ->
    ensure_table(),
    case ets:last(?TABLE) of
        '$end_of_table' -> 1;
        Cursor -> Cursor + 1
    end.

dropped_events() ->
    persistent_term:get(?DROPPED_KEY, 0).

increment_dropped() ->
    persistent_term:put(?DROPPED_KEY, dropped_events() + 1),
    io:format("[M-055][runtime_telemetry][DROP_OVERFLOW] dropped=~p~n", [dropped_events()]),
    ok.
%% END_BLOCK_TABLE_HELPERS

%% START_BLOCK_EMIT_EVENT
emit_event(Event0) when is_map(Event0) ->
    ensure_table(),
    case ets:info(?TABLE, size) >= ?MAX_BUFFER of
        true ->
            increment_dropped();
        false ->
            Cursor = next_cursor(),
            Event = safe_event(Cursor, Event0),
            ets:insert(?TABLE, {Cursor, Event}),
            io:format("[M-055][runtime_telemetry][EMIT_EVENT] cursor=~p event_type=~p~n", [
                Cursor,
                maps:get(event_type, Event, <<"unknown">>)
            ]),
            ok
    end.
%% END_BLOCK_EMIT_EVENT

%% START_BLOCK_METRIC_COUNTERS
add_metric(Key, Value) when is_integer(Value), Value > 0 ->
    ensure_metric_table(),
    ets:update_counter(?METRIC_TABLE, Key, Value, {Key, 0}),
    ok;
add_metric(_Key, _Value) ->
    ok.

drain_metric_counters() ->
    ensure_metric_table(),
    Counters = ets:tab2list(?METRIC_TABLE),
    ets:delete_all_objects(?METRIC_TABLE),
    Counters.

active_domain_counts() ->
    case ets:info(mtp_policy_counter) of
        undefined ->
            [];
        _Info ->
            lists:filtermap(
              fun
                  ({[Domain], Count}) when is_binary(Domain), is_integer(Count), Count > 0 ->
                      {true, {Domain, Count}};
                  (_) ->
                      false
              end,
              ets:tab2list(mtp_policy_counter))
    end.
%% END_BLOCK_METRIC_COUNTERS

%% START_BLOCK_SNAPSHOT
snapshot() ->
    ensure_table(),
    ActiveDomains = active_domain_counts(),
    ActiveConnections = lists:sum([Count || {_Domain, Count} <- ActiveDomains]),
    Last = case ets:last(?TABLE) of
        '$end_of_table' -> null;
        Cursor -> Cursor
    end,
    Snapshot = #{
        status => <<"healthy">>,
        buffered_events => ets:info(?TABLE, size),
        dropped_events => dropped_events(),
        active_connections => ActiveConnections,
        active_domain_count => length(ActiveDomains),
        policy_count => policy_count(),
        last_event_id => Last,
        resource_metrics => resource_metrics()
    },
    io:format("[M-055][telemetry_snapshot][SNAPSHOT] buffered=~p dropped=~p~n", [
        maps:get(buffered_events, Snapshot),
        maps:get(dropped_events, Snapshot)
    ]),
    Snapshot.
%% END_BLOCK_SNAPSHOT

%% START_BLOCK_DRAIN
drain(Cursor0, Limit0) ->
    ensure_table(),
    Cursor = max(0, Cursor0),
    Limit = min(max(1, Limit0), 1000),
    Events = collect(Cursor + 1, Limit, []),
    NextCursor = case Events of
        [] -> Cursor;
        _ -> maps:get(cursor, lists:last(Events), Cursor)
    end,
    io:format("[M-055][telemetry_drain][DRAIN_EVENTS] cursor=~p returned=~p next_cursor=~p~n", [
        Cursor,
        length(Events),
        NextCursor
    ]),
    #{
        status => <<"ok">>,
        events => Events,
        next_cursor => NextCursor,
        dropped_events => dropped_events()
    }.

collect(_Cursor, 0, Acc) ->
    lists:reverse(Acc);
collect(Cursor, Limit, Acc) ->
    case ets:next(?TABLE, Cursor - 1) of
        '$end_of_table' ->
            lists:reverse(Acc);
        Next ->
            [{Next, Event}] = ets:lookup(?TABLE, Next),
            collect(Next + 1, Limit - 1, [Event#{cursor => Next} | Acc])
    end.
%% END_BLOCK_DRAIN

%% START_BLOCK_SAFE_EVENT
safe_event(Cursor, Event) ->
    EventType = safe_binary(maps:get(event_type, Event, <<"error">>)),
    RuntimeEventId = case maps:get(runtime_event_id, Event, undefined) of
        undefined -> <<"runtime-", (integer_to_binary(Cursor))/binary>>;
        Value -> safe_binary(Value)
    end,
    #{
        runtime_event_id => RuntimeEventId,
        event_type => EventType,
        observed_at => safe_binary(maps:get(observed_at, Event, <<"">>)),
        assignment_id => safe_integer(maps:get(assignment_id, Event, null)),
        user_id => safe_integer(maps:get(user_id, Event, null)),
        sni => safe_binary(maps:get(sni, Event, <<"">>)),
        ip_hash => safe_binary(maps:get(ip_hash, Event, <<"">>)),
        ip_prefix => safe_binary(maps:get(ip_prefix, Event, <<"">>)),
        bytes_in => safe_integer(maps:get(bytes_in, Event, 0)),
        bytes_out => safe_integer(maps:get(bytes_out, Event, 0)),
        duration_ms => safe_integer(maps:get(duration_ms, Event, 0)),
        connection_count => safe_integer(maps:get(connection_count, Event, 0)),
        error_code => safe_binary(maps:get(error_code, Event, <<"">>)),
        reason_code => safe_binary(maps:get(reason_code, Event, <<"">>))
    }.

safe_binary(Value) when is_binary(Value) ->
    case byte_size(Value) > 160 of
        true -> binary:part(Value, 0, 160);
        false -> Value
    end;
safe_binary(Value) when is_list(Value) ->
    safe_binary(unicode:characters_to_binary(Value));
safe_binary(Value) when is_atom(Value) ->
    atom_to_binary(Value);
safe_binary(Value) when is_integer(Value) ->
    integer_to_binary(Value);
safe_binary(_) ->
    <<>>.

safe_integer(null) ->
    null;
safe_integer(Value) when is_integer(Value), Value >= 0 ->
    Value;
safe_integer(Value) when is_binary(Value) ->
    case string:to_integer(binary_to_list(Value)) of
        {Int, _} when Int >= 0 -> Int;
        _ -> 0
    end;
safe_integer(_) ->
    0.

policy_count() ->
    case whereis(mtp_policy_table) of
        undefined -> 0;
        _Pid -> mtp_policy_table:table_size(personal_domains)
    end.

resource_metrics() ->
    {RuntimeTotal, RuntimeDelta} = erlang:statistics(runtime),
    {WallTotal, WallDelta} = erlang:statistics(wall_clock),
    Schedulers = max(erlang:system_info(schedulers_online), 1),
    CpuPercent = case WallDelta > 0 of
        true -> min(100, round((RuntimeDelta * 100) / (WallDelta * Schedulers)));
        false -> 0
    end,
    #{
        cpu_percent => CpuPercent,
        runtime_total_ms => RuntimeTotal,
        memory_rss_bytes => erlang:memory(total),
        memory_total_bytes => erlang:memory(total),
        memory_processes_bytes => erlang:memory(processes),
        process_count => erlang:system_info(process_count),
        run_queue => erlang:statistics(run_queue),
        uptime_seconds => WallTotal div 1000
    }.
%% END_BLOCK_SAFE_EVENT
