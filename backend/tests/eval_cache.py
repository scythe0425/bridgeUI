"""
eval_cache.py — 캐시 파이프라인(Stage 1/2) 정확도 평가

seed에 쓰지 않은 실제 해상도 스크린샷에서 /detect와 같은 방식(conf 0.3)으로 UI 박스를
뽑고, 사용자가 그 박스를 탭했을 때 Stage 1/2가 돌려주는 캐시 항목이 맞는 설명인지 측정합니다.

라벨 단위는 (박스, 반환된 설명 문장) 쌍입니다. 항목 ID가 아니라 설명으로 판정하므로,
임베딩이 같은 중복 항목 중 어느 것이 1위로 나와도 같은 라벨이 적용됩니다.

사용법 (backend/ 에서 실행):
    venv/bin/python3 tests/eval_cache.py build      # 박스 탐지 + 크롭 저장 (최초 1회, 수 분)
    venv/bin/python3 tests/eval_cache.py sheet      # 라벨이 필요한 쌍을 시트 이미지로 출력
    venv/bin/python3 tests/eval_cache.py label "0:1,1:0"   # 시트 번호별 판정 반영 (1=맞음)
    venv/bin/python3 tests/eval_cache.py run        # 현재 코드로 정확도 측정

파일:
    tests/eval/boxes.json   박스 목록 (커밋 대상)
    tests/eval/labels.json  {박스 키: {설명 문장: true/false}} (커밋 대상)
    tests/eval/crops/       박스 크롭 PNG (gitignore — 스크린샷에서 재생성 가능)
    tests/eval/sheets/      라벨링용 시트 이미지 (gitignore)
"""

import argparse
import builtins
import io
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

EVAL_DIR = BACKEND / "tests" / "eval"
CROP_DIR = EVAL_DIR / "crops"
SHEET_DIR = EVAL_DIR / "sheets"
BOXES_FILE = EVAL_DIR / "boxes.json"
LABELS_FILE = EVAL_DIR / "labels.json"
SCREENSHOT_DIR = BACKEND / "db" / "screenshots"

# seed_db.APP_CONFIG에 포함되지 않은 네이버 지도 스크린샷 (평가 전용)
EVAL_SCREENSHOTS = [
    "naver_map_2.png", "naver_map_3.png", "naver_map_4.png", "naver_map_5.png",
    "naver_map_directions.png", "naver_map_directions_2.png",
    "naver_map_directions_3.png", "naver_map_directions_6.png",
]
APP_PACKAGE = "com.nhn.android.nmap"

DETECT_CONF = 0.3          # /detect 엔드포인트와 동일
CANDIDATE_MIN_SIM = 0.85   # 이보다 낮은 CLIP 후보는 어떤 규칙에서도 히트하지 않으므로 라벨 불필요
CANDIDATE_MAX_HAMMING = 8  # Stage 1 동일앱 임계값


def _quiet(fn, *args, **kwargs):
    """ui_detector의 print 로그를 숨기고 함수를 호출합니다."""
    original = builtins.print
    builtins.print = lambda *a, **k: None
    try:
        return fn(*args, **kwargs)
    finally:
        builtins.print = original


def _box_key(shot: str, box: list[int]) -> str:
    """박스를 식별하는 문자열 키를 만듭니다."""
    return f"{shot}:{box[0]},{box[1]},{box[2]},{box[3]}"


def _load_json(path: Path, default):
    """JSON 파일을 읽습니다. 없으면 기본값을 반환합니다."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _category_packages() -> list[str]:
    """평가 앱이 속한 카테고리 패키지 목록을 main.py와 같은 규칙으로 반환합니다."""
    from main import _get_category_packages
    return _get_category_packages(APP_PACKAGE)


def build() -> None:
    """평가 스크린샷에서 박스를 탐지하고, /capture와 같은 방식으로 요소 크롭을 저장합니다."""
    from PIL import Image
    from pipeline.ui_detector import _get_model, detect_from_full_screenshot

    CROP_DIR.mkdir(parents=True, exist_ok=True)
    boxes = []
    for shot in EVAL_SCREENSHOTS:
        path = SCREENSHOT_DIR / shot
        if not path.exists():
            print(f"[skip] 스크린샷 없음: {path}")
            continue
        data = path.read_bytes()
        image = Image.open(io.BytesIO(data)).convert("RGB")
        result = _get_model().predict(image, verbose=False, conf=DETECT_CONF)
        for xyxy in result[0].boxes.xyxy:
            box = [int(v) for v in xyxy.tolist()]
            detection = _quiet(detect_from_full_screenshot, data, *box)
            key = _box_key(shot, box)
            crop_name = key.replace(":", "_").replace(",", "_").replace(".png", "") + ".png"
            (CROP_DIR / crop_name).write_bytes(detection["element_image_bytes"])
            boxes.append({
                "key": key,
                "screenshot": shot,
                "box": box,
                "crop": crop_name,
                "element_type": detection["element_type"],
                "fallback": detection["fallback"],
            })
        print(f"[build] {shot}: 누적 {len(boxes)}개")
    BOXES_FILE.write_text(json.dumps(boxes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[build] {BOXES_FILE} 저장 — 박스 {len(boxes)}개")


def _candidates(boxes: list[dict]) -> list[tuple[dict, str, str, str]]:
    """박스마다 Stage 1/2가 반환할 수 있는 상위 후보 (박스, 항목 ID, 출처, 설명) 목록을 만듭니다."""
    from db.chroma_store import get_collection
    from pipeline import hash_track
    from pipeline.embedder import embed_image

    collection = get_collection()
    hash_track.load_from_collection(collection)
    cats = set(_category_packages())
    pairs = []
    for b in boxes:
        crop = (CROP_DIR / b["crop"]).read_bytes()
        # Stage 1 후보: 카테고리 내 해밍 거리 최소 항목 (동점이면 모두)
        ph = hash_track.compute(crop)
        scored = []
        for elem_id, (stored, desc, _t, pkg) in hash_track._store.items():
            if pkg in cats and desc and (ph - stored) <= CANDIDATE_MAX_HAMMING:
                scored.append((ph - stored, elem_id, desc))
        if scored:
            best = min(d for d, _i, _s in scored)
            for dist, elem_id, desc in scored:
                if dist == best:
                    pairs.append((b, elem_id, f"hash d={dist}", desc))
        # Stage 2 후보: 카테고리 내 CLIP 유사도 최고 항목 (근사 검색 순서가 흔들리는 동점은 모두)
        q = collection.query(
            query_embeddings=[embed_image(crop)], n_results=5,
            where={"app_package": {"$in": sorted(cats)}},
            include=["metadatas", "distances"],
        )
        if q["ids"][0]:
            top = 1.0 - q["distances"][0][0]
            for elem_id, dist, meta in zip(q["ids"][0], q["distances"][0], q["metadatas"][0]):
                sim = 1.0 - dist
                if sim >= CANDIDATE_MIN_SIM and top - sim <= 0.001:
                    pairs.append((b, elem_id, f"clip s={sim:.3f}", meta.get("description", "")))
    return pairs


def sheet() -> None:
    """라벨이 없는 (박스, 항목) 쌍을 화면 맥락과 설명이 함께 보이는 시트 이미지로 출력합니다."""
    import textwrap
    from PIL import Image, ImageDraw, ImageFont

    boxes = _load_json(BOXES_FILE, [])
    if not boxes:
        sys.exit("boxes.json이 없습니다. 먼저 build를 실행하세요.")
    labels = _load_json(LABELS_FILE, {})
    pairs = [p for p in _candidates(boxes) if p[3] not in labels.get(p[0]["key"], {})]
    seen, todo = set(), []
    for p in pairs:
        if (p[0]["key"], p[3]) not in seen:
            seen.add((p[0]["key"], p[3]))
            todo.append(p)

    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    for old in SHEET_DIR.glob("*"):
        old.unlink()
    font_path = next((f for f in ["/mnt/c/Windows/Fonts/malgun.ttf",
                                  "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"]
                      if Path(f).exists()), None)
    font = ImageFont.truetype(font_path, 15) if font_path else ImageFont.load_default()

    cell_w, img_h, text_h, cols, rows = 380, 230, 80, 4, 4
    per_sheet = cols * rows
    index = []
    screenshots: dict[str, Image.Image] = {}
    for s in range(0, len(todo), per_sheet):
        canvas = Image.new("RGB", (cell_w * cols, (img_h + text_h) * rows), "white")
        draw = ImageDraw.Draw(canvas)
        for i, (b, elem_id, source, desc) in enumerate(todo[s:s + per_sheet]):
            n = s + i
            shot = screenshots.setdefault(
                b["screenshot"], Image.open(SCREENSHOT_DIR / b["screenshot"]).convert("RGB"))
            x1, y1, x2, y2 = b["box"]
            pad_x, pad_y = max(120, (x2 - x1)), max(80, (y2 - y1))
            region = (max(0, x1 - pad_x), max(0, y1 - pad_y),
                      min(shot.width, x2 + pad_x), min(shot.height, y2 + pad_y))
            ctx = shot.crop(region).copy()
            ImageDraw.Draw(ctx).rectangle(
                (x1 - region[0], y1 - region[1], x2 - region[0], y2 - region[1]),
                outline="red", width=4)
            ctx.thumbnail((cell_w - 10, img_h - 22))
            cx, cy = (i % cols) * cell_w, (i // cols) * (img_h + text_h)
            canvas.paste(ctx, (cx + 5, cy + 20))
            draw.text((cx + 5, cy + 2), f"#{n}  {source}", fill="blue", font=font)
            draw.multiline_text((cx + 5, cy + img_h + 2),
                                "\n".join(textwrap.wrap(desc, 24)[:4]), fill="black", font=font)
            index.append({"n": n, "key": b["key"], "id": elem_id, "source": source, "description": desc})
        out = SHEET_DIR / f"sheet_{s // per_sheet:02d}.png"
        canvas.save(out)
    (SHEET_DIR / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[sheet] 라벨 필요 {len(todo)}쌍 → {SHEET_DIR} (index.json에 번호별 키·ID)")


def apply_labels(judgements: str) -> None:
    """시트 번호별 판정을 labels.json에 반영합니다.

    Args:
        judgements: "0:1,1:0,2:1" 형식. 1은 맞는 설명, 0은 틀린 설명.
    """
    index = {e["n"]: e for e in _load_json(SHEET_DIR / "index.json", [])}
    labels = _load_json(LABELS_FILE, {})
    count = 0
    for item in judgements.split(","):
        if not item.strip():
            continue
        n, v = item.split(":")
        entry = index[int(n)]
        labels.setdefault(entry["key"], {})[entry["description"]] = v.strip() == "1"
        count += 1
    LABELS_FILE.write_text(json.dumps(labels, ensure_ascii=False, indent=1, sort_keys=True),
                           encoding="utf-8")
    print(f"[label] {count}개 반영 → {LABELS_FILE}")


def run() -> None:
    """현재 코드의 Stage 1/2 검색을 그대로 호출해 맞은 히트·틀린 히트·미스를 셉니다."""
    from db.chroma_store import get_collection
    from pipeline.embedder import embed_image
    from pipeline.fast_track import search as fast_search
    from pipeline.hash_track import load_from_collection, search as hash_search

    boxes = _load_json(BOXES_FILE, [])
    if not boxes:
        sys.exit("boxes.json이 없습니다. 먼저 build를 실행하세요.")
    labels = _load_json(LABELS_FILE, {})
    load_from_collection(get_collection())
    cats = _category_packages()

    stats = {f"{t}_{r}": 0 for t in ("hash", "fast") for r in ("ok", "bad", "unlabeled")}
    stats["miss"] = 0
    wrong = []
    for b in boxes:
        crop = (CROP_DIR / b["crop"]).read_bytes()
        result = hash_search(crop, app_packages=cats, own_package=APP_PACKAGE)
        track = "hash"
        if not result:
            result = fast_search(embed_image(crop), app_packages=cats, own_package=APP_PACKAGE)
            track = "fast"
        if not result:
            stats["miss"] += 1
            continue
        verdict = labels.get(b["key"], {}).get(result["description"])
        if verdict is None:
            stats[f"{track}_unlabeled"] += 1
        elif verdict:
            stats[f"{track}_ok"] += 1
        else:
            stats[f"{track}_bad"] += 1
            wrong.append((b["key"], track, result["description"][:40]))

    total = len(boxes)
    hits_ok = stats["hash_ok"] + stats["fast_ok"]
    hits_bad = stats["hash_bad"] + stats["fast_bad"]
    unlabeled = stats["hash_unlabeled"] + stats["fast_unlabeled"]
    print(f"박스 {total}개")
    print(f"  Stage 1 hash : 맞음 {stats['hash_ok']:3d} / 틀림 {stats['hash_bad']:3d} / 라벨없음 {stats['hash_unlabeled']}")
    print(f"  Stage 2 fast : 맞음 {stats['fast_ok']:3d} / 틀림 {stats['fast_bad']:3d} / 라벨없음 {stats['fast_unlabeled']}")
    print(f"  미스(Gemini) : {stats['miss']:3d}")
    labeled_hits = hits_ok + hits_bad
    if labeled_hits:
        print(f"  틀린 히트 비율 : {hits_bad / labeled_hits:.1%} ({hits_bad}/{labeled_hits})")
    print(f"  맞는 캐시 응답 비율 : {hits_ok / total:.1%}")
    if unlabeled:
        print(f"  ⚠ 라벨 없는 히트 {unlabeled}개 — sheet로 라벨을 추가하세요.")


def main() -> None:
    """명령행 인자에 따라 build / sheet / label / run을 실행합니다."""
    parser = argparse.ArgumentParser(description="캐시 파이프라인 정확도 평가")
    parser.add_argument("command", choices=["build", "sheet", "label", "run"])
    parser.add_argument("judgements", nargs="?", default="",
                        help='label 명령용: "번호:1|0,..." (1=맞음, 0=틀림)')
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "sheet":
        sheet()
    elif args.command == "label":
        apply_labels(args.judgements)
    else:
        run()


if __name__ == "__main__":
    main()
