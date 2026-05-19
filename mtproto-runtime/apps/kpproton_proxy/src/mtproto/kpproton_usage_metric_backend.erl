-module(kpproton_usage_metric_backend).

%% FILE: apps/kpproton_proxy/src/mtproto/kpproton_usage_metric_backend.erl
%% VERSION: 1.0.0
%% START_MODULE_CONTRACT
%%   PURPOSE: Convert mtproto_proxy hot-path metrics into bounded KrotPN usage telemetry counters.
%%   SCOPE: Secret-free global byte counters, protocol error counters, protocol-ok counters, and connection counters.
%%   DEPENDS: M-PROXY-BRIDGE, M-055
%%   LINKS: M-055
%% END_MODULE_CONTRACT
%%
%% START_MODULE_MAP
%%   notify/4 - mtproto_proxy metric_backend callback that records safe counters
%% END_MODULE_MAP
%%
%% START_CHANGE_SUMMARY
%%   LAST_CHANGE: v1.0.0 - Added Phase-42 mtproto_proxy metric backend bridge.
%% END_CHANGE_SUMMARY

-export([notify/4]).

%% START_BLOCK_NOTIFY_METRIC
notify(count, [mtproto_proxy, received, upstream, bytes], Value, _Extra) ->
    kpproton_usage_telemetry:add_metric(bytes_in, safe_count(Value));
notify(count, [mtproto_proxy, sent, upstream, bytes], Value, _Extra) ->
    kpproton_usage_telemetry:add_metric(bytes_out, safe_count(Value));
notify(count, [mtproto_proxy, protocol_error, total], Value, Extra) ->
    Reason = safe_label(label_at(2, Extra, unknown)),
    kpproton_usage_telemetry:add_metric({protocol_error, Reason}, safe_count(Value));
notify(count, [mtproto_proxy, protocol_ok, total], Value, Extra) ->
    Protocol = safe_label(label_at(2, Extra, unknown)),
    kpproton_usage_telemetry:add_metric({protocol_ok, Protocol}, safe_count(Value));
notify(count, [mtproto_proxy, in_connection, total], Value, _Extra) ->
    kpproton_usage_telemetry:add_metric(in_connections, safe_count(Value));
notify(count, [mtproto_proxy, in_connection_closed, total], Value, _Extra) ->
    kpproton_usage_telemetry:add_metric(closed_connections, safe_count(Value));
notify(_Type, _Name, _Value, _Extra) ->
    ok.
%% END_BLOCK_NOTIFY_METRIC

%% START_BLOCK_SAFE_LABELS
safe_count(Value) when is_integer(Value), Value > 0 ->
    Value;
safe_count(_) ->
    0.

label_at(Position, #{labels := Labels}, Default) when is_list(Labels), Position > 0 ->
    case length(Labels) >= Position of
        true -> lists:nth(Position, Labels);
        false -> Default
    end;
label_at(_Position, _Extra, Default) ->
    Default.

safe_label(Value) when is_binary(Value), byte_size(Value) =< 80 ->
    Value;
safe_label(Value) when is_binary(Value) ->
    binary:part(Value, 0, 80);
safe_label(Value) when is_atom(Value) ->
    safe_label(atom_to_binary(Value, utf8));
safe_label(Value) when is_integer(Value) ->
    safe_label(integer_to_binary(Value));
safe_label(Value) when is_list(Value) ->
    safe_label(unicode:characters_to_binary(Value));
safe_label(_) ->
    <<"unknown">>.
%% END_BLOCK_SAFE_LABELS
