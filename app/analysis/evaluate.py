import argparse
import csv
import itertools
import json
import os

from segment import find_rallies
from trajectory import build_ball_track, load_detections


def iou(a, b):
    inter = min(a["end"], b["end"]) - max(a["start"], b["start"])
    union = max(a["end"], b["end"]) - min(a["start"], b["start"])
    return max(inter, 0.0) / union if union > 0 else 0.0


def prf(auto, manual, iou_thr):
    hit_auto = {i for i, a in enumerate(auto)
                if any(iou(a, m) >= iou_thr for m in manual)}
    hit_manual = {j for j, m in enumerate(manual)
                  if any(iou(a, m) >= iou_thr for a in auto)}
    precision = len(hit_auto) / len(auto) if auto else 0.0
    recall = len(hit_manual) / len(manual) if manual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def load_cases(cases_dir, params):
    cases = []
    for name in sorted(os.listdir(cases_dir)):
        d = os.path.join(cases_dir, name)
        if not os.path.isfile(os.path.join(d, "manual.json")):
            continue
        with open(os.path.join(d, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(d, "manual.json"), encoding="utf-8") as f:
            manual = json.load(f)["rallies"]
        frames = load_detections(os.path.join(d, "detections.csv"))
        track = build_ball_track(frames, meta["n_frames"],
                                 ball_name=params["ball_name"],
                                 ball_conf_min=params["ball_conf_min"])
        cases.append({"name": name, "meta": meta, "manual": manual, "track": track})
    return cases


def run_grid(cases, params, iou_thr):
    keys = list(params["grid"].keys())
    rows = []
    for values in itertools.product(*(params["grid"][k] for k in keys)):
        p = dict(params)
        p.update(zip(keys, values))

        scores = []
        for c in cases:
            auto = find_rallies(c["track"], c["meta"]["fps"], c["meta"]["width"], p)
            scores.append(prf(auto, c["manual"], iou_thr))

        n = len(scores)
        row = dict(zip(keys, values))
        row["precision"] = round(sum(s[0] for s in scores) / n, 3)
        row["recall"] = round(sum(s[1] for s in scores) / n, 3)
        row["f1"] = round(sum(s[2] for s in scores) / n, 3)
        rows.append(row)
    return sorted(rows, key=lambda r: r["f1"], reverse=True)


def main():
    import yaml

    ap = argparse.ArgumentParser(description="Оценка алгоритма и перебор параметров")
    ap.add_argument("--cases", default="data", help="папка с видео и manual.json")
    ap.add_argument("--params", default="params.yaml", help="файл параметров")
    ap.add_argument("--out", default="grid_results.csv", help="куда сохранить таблицу")
    ap.add_argument("--iou", type=float, default=0.5, help="порог совпадения интервалов")
    args = ap.parse_args()

    with open(args.params, encoding="utf-8") as f:
        params = yaml.safe_load(f)

    cases = load_cases(args.cases, params)
    if not cases:
        raise SystemExit(f"В {args.cases} нет папок с manual.json")
    print("Видео для оценки:", [c["name"] for c in cases])

    rows = run_grid(cases, params, args.iou)
    if not rows:
        raise SystemExit("В params.yaml нет секции grid")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print("Лучшие комбинации по F1:")
    for r in rows[:10]:
        print(r)
    print(f"Полная таблица: {args.out}")


if __name__ == "__main__":
    main()