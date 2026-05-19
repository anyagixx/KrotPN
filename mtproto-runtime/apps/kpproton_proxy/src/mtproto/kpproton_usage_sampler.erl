-module(kpproton_usage_sampler).
-behaviour(gen_server).

%% FILE: apps/kpproton_proxy/src/mtproto/kpproton_usage_sampler.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Sample live mtproto_proxy runtime counters into secret-free KrotPN usage events.
%%   SCOPE: Active per-SNI connection deltas, global/single-active-domain traffic attribution, protocol error events, and req_pq proof hints.
%%   DEPENDS: M-PROXY-BRIDGE, M-055
%%   LINKS: M-055
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   start_link/0 - starts the periodic usage telemetry sampler
%%   init/1 - initializes sampler state and timer
%%   handle_info/2 - drains counters and samples active SNI state
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added Phase-42 live runtime sampler for mtproto_proxy counters.
%% END_CHANGE_SUMMARY

-export([start_link/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-define(DEFAULT_SAMPLE_INTERVAL_MS, 15000).

%% START_BLOCK_START_LINK
start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).
%% END_BLOCK_START_LINK

%% START_BLOCK_INIT
init([]) ->
    Interval = sample_interval_ms(),
    erlang:send_after(1000, self(), sample),
    {ok, #{interval => Interval, active_counts => #{}, starts => #{}}}.
%% END_BLOCK_INIT

%% START_BLOCK_GEN_SERVER_CALLBACKS
handle_call(_Msg, _From, State) ->
    {reply, ok, State}.

handle_cast(_Msg, State) ->
    {noreply, State}.

handle_info(sample, State) ->
    NewState =
        try sample(State)
        catch Class:Reason:Stack ->
                io:format("[M-055][usage_sampler][SAMPLE_ERROR] class=~p reason=~p stack=~p~n", [
                    Class,
                    Reason,
                    Stack
                ]),
                State
        end,
    erlang:send_after(maps:get(interval, NewState, ?DEFAULT_SAMPLE_INTERVAL_MS), self(), sample),
    {noreply, NewState};
handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.
%% END_BLOCK_GEN_SERVER_CALLBACKS

%% START_BLOCK_SAMPLE
sample(State) ->
    NowMs = erlang:system_time(millisecond),
    ActivePairs = kpproton_usage_telemetry:active_domain_counts(),
    ActiveCounts = maps:from_list(ActivePairs),
    PrevCounts = maps:get(active_counts, State, #{}),
    Starts0 = maps:get(starts, State, #{}),
    Starts1 = emit_domain_deltas(ActiveCounts, PrevCounts, Starts0, NowMs),
    emit_metric_events(kpproton_usage_telemetry:drain_metric_counters(), ActiveCounts),
    State#{active_counts => ActiveCounts, starts => Starts1}.
%% END_BLOCK_SAMPLE

%% START_BLOCK_DOMAIN_DELTAS
emit_domain_deltas(ActiveCounts, PrevCounts, Starts0, NowMs) ->
    Domains = ordsets:union(ordsets:from_list(maps:keys(ActiveCounts)), ordsets:from_list(maps:keys(PrevCounts))),
    lists:foldl(
      fun(Domain, StartsAcc) ->
              Curr = maps:get(Domain, ActiveCounts, 0),
              Prev = maps:get(Domain, PrevCounts, 0),
              StartsNext = emit_domain_delta(Domain, Curr, Prev, StartsAcc, NowMs),
              case Curr > 0 orelse Curr =/= Prev of
                  true ->
                      emit_event(#{
                          event_type => <<"active_connection">>,
                          sni => Domain,
                          connection_count => Curr,
                          reason_code => <<"policy_counter_sample">>
                      });
                  false ->
                      ok
              end,
              StartsNext
      end,
      Starts0,
      Domains).

emit_domain_delta(Domain, Curr, Prev, Starts, NowMs) when Curr > Prev ->
    Diff = Curr - Prev,
    emit_event(#{
        event_type => <<"handshake">>,
        sni => Domain,
        connection_count => Diff,
        reason_code => <<"policy_counter_increment">>
    }),
    push_starts(Domain, Diff, NowMs, Starts);
emit_domain_delta(Domain, Curr, Prev, Starts, NowMs) when Curr < Prev ->
    Diff = Prev - Curr,
    {DurationMs, Starts1} = pop_starts(Domain, Diff, NowMs, Starts),
    emit_event(#{
        event_type => <<"close">>,
        sni => Domain,
        connection_count => Diff,
        duration_ms => DurationMs,
        reason_code => <<"policy_counter_decrement">>
    }),
    Starts1;
emit_domain_delta(_Domain, _Curr, _Prev, Starts, _NowMs) ->
    Starts.

push_starts(Domain, Diff, NowMs, Starts) ->
    Existing = maps:get(Domain, Starts, []),
    maps:put(Domain, lists:duplicate(Diff, NowMs) ++ Existing, Starts).

pop_starts(Domain, Diff, NowMs, Starts) ->
    Existing = maps:get(Domain, Starts, []),
    {Closed, Rest} = split_count(Diff, Existing),
    DurationMs = lists:sum([max(NowMs - Started, 0) || Started <- Closed]),
    Starts1 = case Rest of
        [] -> maps:remove(Domain, Starts);
        _ -> maps:put(Domain, Rest, Starts)
    end,
    {DurationMs, Starts1}.

split_count(Count, Items) when Count =< 0 ->
    {[], Items};
split_count(Count, Items) ->
    split_count(Count, Items, []).

split_count(0, Rest, Acc) ->
    {lists:reverse(Acc), Rest};
split_count(_Count, [], Acc) ->
    {lists:reverse(Acc), []};
split_count(Count, [Item | Rest], Acc) ->
    split_count(Count - 1, Rest, [Item | Acc]).
%% END_BLOCK_DOMAIN_DELTAS

%% START_BLOCK_METRIC_EVENTS
emit_metric_events(Counters, ActiveCounts) ->
    BytesIn = counter_value(bytes_in, Counters),
    BytesOut = counter_value(bytes_out, Counters),
    Attribution = attribution(ActiveCounts),
    case BytesIn > 0 orelse BytesOut > 0 of
        true ->
            emit_event(
              attribution_fields(Attribution, #{
                  event_type => <<"bytes">>,
                  bytes_in => BytesIn,
                  bytes_out => BytesOut,
                  metadata => #{
                      attribution => attribution_name(Attribution),
                      active_domain_count => maps:size(ActiveCounts)
                  }
              }));
        false ->
            ok
    end,
    emit_protocol_events(Counters, Attribution),
    ok.

emit_protocol_events(Counters, Attribution) ->
    lists:foreach(
      fun
          ({{protocol_error, Reason}, Count}) when Count > 0 ->
              emit_event(
                attribution_fields(Attribution, #{
                    event_type => classify_protocol_error(Reason),
                    connection_count => Count,
                    reason_code => Reason
                }));
          ({{protocol_ok, Protocol}, Count}) when Count > 0 ->
              emit_event(
                attribution_fields(Attribution, #{
                    event_type => <<"req_pq_proof">>,
                    connection_count => Count,
                    reason_code => Protocol
                }));
          (_) ->
              ok
      end,
      Counters).

counter_value(Key, Counters) ->
    case lists:keyfind(Key, 1, Counters) of
        {Key, Value} when is_integer(Value), Value > 0 -> Value;
        _ -> 0
    end.

attribution(ActiveCounts) when map_size(ActiveCounts) =:= 1 ->
    [{Domain, _Count}] = maps:to_list(ActiveCounts),
    {single_active_domain, Domain};
attribution(_ActiveCounts) ->
    global_runtime.

attribution_fields({single_active_domain, Domain}, Event) ->
    Event#{sni => Domain};
attribution_fields(global_runtime, Event) ->
    Event.

attribution_name({single_active_domain, _Domain}) ->
    <<"single_active_domain">>;
attribution_name(global_runtime) ->
    <<"global_runtime">>.

classify_protocol_error(<<"policy_error">>) ->
    <<"rejected_sni">>;
classify_protocol_error(<<"tls_no_sni">>) ->
    <<"unknown_sni">>;
classify_protocol_error(<<"tls_bad_client_hello">>) ->
    <<"unknown_sni">>;
classify_protocol_error(_Reason) ->
    <<"error">>.
%% END_BLOCK_METRIC_EVENTS

%% START_BLOCK_HELPERS
emit_event(Event) ->
    catch kpproton_usage_telemetry:emit_event(Event),
    ok.

sample_interval_ms() ->
    case string:to_integer(env_string("MTPROTO_TELEMETRY_SAMPLE_INTERVAL_MS", integer_to_list(?DEFAULT_SAMPLE_INTERVAL_MS))) of
        {Int, _} when Int >= 1000 -> Int;
        _ -> ?DEFAULT_SAMPLE_INTERVAL_MS
    end.

env_string(Key, Default) ->
    case os:getenv(Key) of
        false -> Default;
        Value -> Value
    end.
%% END_BLOCK_HELPERS
