import csv
import json
from dataclasses import dataclass


@dataclass
class BallPoint:
    x: float
    y: float
    conf: float

def load_detections(csv_path):
    frames = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            det = {
                "cls": row["class"],
                "x": float(row["x"]),
                "y": float(row["y"]),
                "w": float(row["w"]),
                "h": float(row["h"]),
                "conf": float(row["confidence"]),
            }
            frames.setdefault(int(row["frame"]), []).append(det)
    return frames


def build_ball_track(frames, n_frames, ball_name="ball", ball_conf_min=0.3):
    track = [None] * n_frames
    for f in range(n_frames):
        best = None
        for det in frames.get(f, []):
            if det["cls"] != ball_name or det["conf"] < ball_conf_min:
                continue
            if best is None or det["conf"] > best["conf"]:
                best = det
        if best is not None:
            track[f] = BallPoint(best["x"] + best["w"] / 2,
                                 best["y"] + best["h"] / 2,
                                 best["conf"])
    return track


def write_timeseries(frames, track, path, player_name="player"):
    with open(path, "w", encoding="utf-8") as f:
        for i, p in enumerate(track):
            players = [
                [round(d["x"], 1), round(d["y"], 1), round(d["w"], 1),
                 round(d["h"], 1), round(d["conf"], 3)]
                for d in frames.get(i, []) if d["cls"] == player_name
            ]
            row = {"frame": i, "ball_x": None, "ball_y": None,
                   "ball_confidence": None, "players": players}
            if p is not None:
                row["ball_x"] = round(p.x, 1)
                row["ball_y"] = round(p.y, 1)
                row["ball_confidence"] = round(p.conf, 3)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")