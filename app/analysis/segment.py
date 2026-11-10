import argparse
import json
import math
import os

from trajectory import build_ball_track, load_detections, write_timeseries


def fill_short_gaps(flags, max_gap):
    out = list(flags)
    n = len(out)
    i = 0
    while i < n:
        if out[i]:
            i += 1
            continue
        j = i
        while j < n and not out[j]:
            j += 1
        if i > 0 and j < n and (j - i) <= max_gap:
            for k in range(i, j):
                out[k] = True
        i = j
    return out


def moving_flags(track, max_gap, min_speed):
    flags = [False] * len(track)
    prev = None      # (номер кадра, точка) последней детекции
    moving = False
    for f, p in enumerate(track):
        if p is None:
            if prev is not None and f - prev[0] > max_gap:
                prev, moving = None, False
        else:
            if prev is not None and f - prev[0] <= max_gap:
                dist = math.hypot(p.x - prev[1].x, p.y - prev[1].y)
                moving = dist / (f - prev[0]) >= min_speed
            else:
                moving = False
            prev = (f, p)
        flags[f] = moving
    return flags


def runs(flags):
    out, start = [], None
    for i, v in enumerate(flags):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def merge_runs(segments, max_gap):
    merged = []
    for s, e in segments:
        if merged and s - merged[-1][1] - 1 <= max_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def find_rallies(track, fps, width, p):
    visible = fill_short_gaps([pt is not None for pt in track],
                              int(p["max_gap_sec"] * fps))
    move = moving_flags(track, int(p["max_gap_sec"] * fps),
                        p["min_speed_frac"] * width)
    game = [v and m for v, m in zip(visible, move)]

    segments = merge_runs(runs(game), int(p["merge_gap_sec"] * fps))
    min_frames = p["min_rally_sec"] * fps
    segments = [(s, e) for s, e in segments if (e - s + 1) >= min_frames]

    # Конец интервала — конец последнего кадра розыгрыша
    return [{"start": round(s / fps, 2), "end": round((e + 1) / fps, 2)}
            for s, e in segments]


def main():
    import yaml

    ap = argparse.ArgumentParser(description="Поиск розыгрышей в детекциях")
    ap.add_argument("--data", required=True, help="папка с detections.csv и meta.json")
    ap.add_argument("--params", default="params.yaml", help="файл параметров")
    ap.add_argument("--out", required=True, help="куда записать rallies.json")
    ap.add_argument("--timeseries", default=None,
                    help="необязательно: записать временной ряд (кадр, мяч, игроки)")
    args = ap.parse_args()

    with open(os.path.join(args.data, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(args.params, encoding="utf-8") as f:
        params = yaml.safe_load(f)

    frames = load_detections(os.path.join(args.data, "detections.csv"))
    track = build_ball_track(frames, meta["n_frames"],
                             ball_name=params["ball_name"],
                             ball_conf_min=params["ball_conf_min"])

    if args.timeseries:
        write_timeseries(frames, track, args.timeseries, player_name=params["player_name"])

    rallies = find_rallies(track, meta["fps"], meta["width"], params)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"rallies": rallies}, f, ensure_ascii=False, indent=2)
    print(f"Найдено розыгрышей: {len(rallies)} -> {args.out}")


if __name__ == "__main__":
    main()