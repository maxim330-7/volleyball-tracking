import argparse
import csv
import json
import os

import cv2
from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser(description="Детекция игроков и мяча в видео")
    ap.add_argument("--video", default=r"backline_volleyball\dinamo_sch10_p2_1080p_h264.mp4", help="путь к видео")
    ap.add_argument("--weights", default=r"backline_volleyball\yolo26s_players_ball.pt", help="путь к весам")
    ap.add_argument("--out", default=r"data\match1", help="папка для результатов")
    ap.add_argument("--conf", type=float, default=0.1,
                    help="низкий порог, чтобы не потерять мяч; отбор делает segment.py")
    ap.add_argument("--device", default=None, help="0 — первая видеокарта, cpu — процессор")
    ap.add_argument("--max-frames", type=int, default=0,
                    help="обработать только первые N кадров (для быстрой проверки); 0 — всё видео")
    args = ap.parse_args()

        # Параметры видео берём через OpenCV: fps нужен для перевода номеров кадров в секунды
    print(f"Попытка открыть видео: {args.video}")
    cap = cv2.VideoCapture(args.video)
    
    # ОБХОД ПРОБЛЕМЫ С КИРИЛЛИЦЕЙ В ПУТИ
    if not cap.isOpened():
        print("Прямое чтение не удалось (кириллица в пути). Пробуем обходной путь через numpy...")
        import numpy as np
        try:
            with open(args.video, 'rb') as f:
                video_bytes = f.read()
            cap = cv2.VideoCapture(np.frombuffer(video_bytes, np.uint8))
        except Exception as e:
            raise SystemExit(f"Критическая ошибка: не удалось прочитать файл. {e}")
            
    if not cap.isOpened():
        raise SystemExit(f"Всё равно не удалось открыть видео: {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if fps <= 0:
        raise SystemExit("Не удалось определить fps видео")

    model = YOLO(args.weights)
    print("Классы модели:", model.names)

    os.makedirs(args.out, exist_ok=True)
    results = model.predict(source=args.video, stream=True, conf=args.conf,
                            device=args.device, verbose=False)

    n_frames = 0
    with open(os.path.join(args.out, "detections.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "class", "x", "y", "w", "h", "confidence"])
        # Каждый элемент results — один кадр видео, по порядку
        for frame_idx, r in enumerate(results):
            if args.max_frames and frame_idx >= args.max_frames:
                break
            n_frames = frame_idx + 1
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue
            # YOLO отдаёт центр и размер прямоугольника, переводим в левый верхний угол
            for (cx, cy, w, h), cls, conf in zip(boxes.xywh.tolist(),
                                                 boxes.cls.tolist(),
                                                 boxes.conf.tolist()):
                writer.writerow([frame_idx, model.names[int(cls)],
                                 round(cx - w / 2, 1), round(cy - h / 2, 1),
                                 round(w, 1), round(h, 1), round(conf, 4)])
            if frame_idx % 500 == 0:
                print(f"обработано кадров: {frame_idx}")

    meta = {
        "video": args.video,
        "fps": fps,
        "width": width,
        "height": height,
        "n_frames": n_frames,
        "class_names": list(model.names.values()),
    }
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Готово: {n_frames} кадров, fps={fps:.2f}, результаты в {args.out}")


if __name__ == "__main__":
    main()