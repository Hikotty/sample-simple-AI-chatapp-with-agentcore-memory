"""検証用 Memory を API で作る（記事ではコンソールで作る想定。設定内容はこれと同じ）。

  uv run --with boto3 scripts/create_memory_for_test.py            # 作成して ACTIVE まで待つ
  uv run --with boto3 scripts/create_memory_for_test.py --delete <memory-id>
"""

import argparse
import sys
import time

import boto3

REGION = "us-east-1"
STRATEGIES = [
    {
        "userPreferenceMemoryStrategy": {
            "name": "UserPreferences",
            "description": "ユーザーの好み・スタイル",
            "namespaceTemplates": ["/users/{actorId}/preferences/"],
        }
    },
    {
        "semanticMemoryStrategy": {
            "name": "UserFacts",
            "description": "ユーザーに関する事実",
            "namespaceTemplates": ["/users/{actorId}/facts/"],
        }
    },
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="memchat_memory_test")
    ap.add_argument("--delete", metavar="MEMORY_ID")
    args = ap.parse_args()
    cp = boto3.client("bedrock-agentcore-control", region_name=REGION)

    if args.delete:
        cp.delete_memory(memoryId=args.delete)
        print(f"deleted {args.delete}")
        return

    resp = cp.create_memory(name=args.name, eventExpiryDuration=7, memoryStrategies=STRATEGIES)
    mid = resp["memory"]["id"]
    print(f"created {mid}; waiting for ACTIVE ...", flush=True)
    for _ in range(60):
        m = cp.get_memory(memoryId=mid)["memory"]
        if m["status"] == "ACTIVE" and all(s["status"] == "ACTIVE" for s in m.get("strategies", [])):
            print(f"ACTIVE: {mid}")
            for s in m["strategies"]:
                print(f"  strategy {s['type']:<16} {s['name']:<16} ns={s['namespaces']}")
            return
        time.sleep(10)
    print("timeout waiting for ACTIVE", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
