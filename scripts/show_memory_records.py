"""ローカルから長期記憶レコードを確認する（AgentCore のデータプレーンは公開エンドポイント）。

  uv run --with boto3 scripts/show_memory_records.py <memory-id> [--actor SUB] [--query "検索文"]

--actor なし: namespacePath "/" 配下（メモリ全体）を ListMemoryRecords で列挙
--actor あり: namespacePath "/users/<sub>/" 配下を列挙（namespace は完全一致なので階層取得には namespacePath を使う）。--query を付けると RetrieveMemoryRecords（セマンティック検索）
"""

import argparse
import os

import boto3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("memory_id")
    ap.add_argument("--actor", help="Cognito sub")
    ap.add_argument("--query", help="セマンティック検索クエリ（--actor 必須）")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    ap.add_argument("--top-k", type=int, default=10)
    args = ap.parse_args()

    dp = boto3.client("bedrock-agentcore", region_name=args.region)
    namespace = f"/users/{args.actor}/" if args.actor else "/"

    if args.query:
        resp = dp.retrieve_memory_records(
            memoryId=args.memory_id,
            namespacePath=namespace,
            searchCriteria={"searchQuery": args.query, "topK": args.top_k},
        )
        print(f"RetrieveMemoryRecords namespace={namespace} query={args.query!r}")
        for r in resp.get("memoryRecordSummaries", []):
            print(f"- score={r.get('score', 0):.3f} ns={r['namespaces'][0]}\n    {r['content']['text']}")
        return

    print(f"ListMemoryRecords namespace={namespace}")
    token = None
    count = 0
    while True:
        kwargs = {"memoryId": args.memory_id, "namespacePath": namespace, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        resp = dp.list_memory_records(**kwargs)
        for r in resp.get("memoryRecordSummaries", []):
            count += 1
            print(f"- [{r['createdAt'].strftime('%m-%d %H:%M')}] ns={r['namespaces'][0]}\n    {r['content']['text']}")
        token = resp.get("nextToken")
        if not token:
            break
    print(f"\ntotal: {count} records")


if __name__ == "__main__":
    main()
