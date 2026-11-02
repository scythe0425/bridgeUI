"""
clean_db.py — ChromaDB에 저장된 잘못된 설명 항목 정리

설명이 중계 메시지("정보를 찾는 중입니다")이거나 잘린 문장인 항목을 찾아 삭제합니다.
이런 항목은 같은 UI를 다시 탭할 때 정상 결과처럼 반환되므로 캐시에 남아 있으면 안 됩니다.
판정 규칙은 pipeline.deep_track.is_valid_description()과 같습니다.

사용법 (backend/ 에서 실행, 서버는 꺼 둔 상태 권장):
    venv/bin/python3 tools/clean_db.py           # 미리보기만 (삭제 없음)
    venv/bin/python3 tools/clean_db.py --apply   # 실제 삭제

실행 중인 서버의 인메모리 pHash 스토어에는 반영되지 않으므로, 삭제 후 서버를 재시작하세요.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.chroma_store import get_collection  # noqa: E402
from pipeline.deep_track import is_valid_description  # noqa: E402


def find_invalid(collection) -> list[tuple[str, dict]]:
    """설명이 유효하지 않은 항목의 (ID, 메타데이터) 목록을 반환합니다.

    Args:
        collection: ChromaDB 컬렉션.

    Returns:
        삭제 대상 항목 목록.
    """
    result = collection.get(include=["metadatas"])
    return [
        (doc_id, meta)
        for doc_id, meta in zip(result["ids"], result["metadatas"])
        if not is_valid_description(meta.get("description", ""))
    ]


def main() -> None:
    """잘못된 항목을 출력하고, --apply가 있으면 삭제합니다."""
    parser = argparse.ArgumentParser(description="ChromaDB 잘못된 설명 항목 정리")
    parser.add_argument("--apply", action="store_true", help="실제로 삭제합니다 (없으면 미리보기)")
    args = parser.parse_args()

    collection = get_collection()
    targets = find_invalid(collection)
    print(f"전체 {collection.count()}개 중 삭제 대상 {len(targets)}개")
    for doc_id, meta in targets:
        print(f"  {doc_id}  app={meta.get('app_package') or '(없음)'}  "
              f"captured_at={meta.get('captured_at', '')}  description={meta.get('description', '')!r}")

    if not targets:
        return
    if not args.apply:
        print("미리보기입니다. 삭제하려면 --apply를 붙여 다시 실행하세요.")
        return
    collection.delete(ids=[doc_id for doc_id, _ in targets])
    print(f"삭제 완료 — 남은 항목 {collection.count()}개. 실행 중인 서버가 있으면 재시작하세요.")


if __name__ == "__main__":
    main()
