"""デモ用の「既存の会話履歴」をアプリの HTTP API 経由で作る（メモリ統合を有効化する前に実行する）。

  uv run --with httpx scripts/seed_demo_history.py --base-url http://<ip>/ --email taro@example.com --password 'Passw0rd123'

ユーザーが存在しなければサインアップし、3 つの会話でそれぞれ数ターンやり取りする。
会話の中身は「あとで長期記憶として思い出されると分かりやすい」個人情報・好みを含む。
"""

import argparse
import json

import httpx

CONVERSATIONS = [
    [
        "はじめまして。私は太郎です。東京在住で、週末はよく高尾山や丹沢に登山に行きます。ひとことで挨拶を返してください。",
        "登山の後に飲むコーヒーが好きで、いつもブラックで飲みます。あなたはコーヒーに合うおやつを何か一つ挙げてください。",
    ],
    [
        "仕事では Python で社内向けの小さな Web ツールをよく作っています。FastAPI を使うことが多いです。FastAPI で SSE を返す最小のコード例を 10 行程度で見せてください。",
        "ありがとう。ちなみに私はフロントエンドはフレームワークを使わず、生の HTML と JavaScript で書く派です。その場合に SSE を受け取る側の注意点を一つ教えてください。",
    ],
    [
        "来月、家族で北海道旅行に行きます。飛行機は窓側の席が好みで、機内食はベジタリアンを選びます。北海道で登山初心者の家族と行ける山を一つ提案してください。",
    ],
]


def sse_final_text(resp: httpx.Response) -> str:
    final = ""
    for line in resp.iter_lines():
        if line.startswith("data: "):
            ev = json.loads(line[6:])
            if ev["type"] == "done":
                final = ev["message"]["content"]
            elif ev["type"] == "error":
                raise RuntimeError(ev["message"])
    return final


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    with httpx.Client(base_url=base, timeout=120) as c:
        r = c.post("/api/auth/signup", json={"email": args.email, "password": args.password})
        if r.status_code == 201:
            print(f"signed up {args.email}")
        elif r.status_code == 409:
            print(f"user exists: {args.email}")
        else:
            r.raise_for_status()
        token = c.post("/api/auth/login", json={"email": args.email, "password": args.password}).raise_for_status().json()["id_token"]
        c.headers["Authorization"] = f"Bearer {token}"
        me = c.get("/api/me").raise_for_status().json()
        print(f"sub (= actorId): {me['sub']}")

        for turns in CONVERSATIONS:
            conv = c.post("/api/conversations").raise_for_status().json()
            print(f"\n== conversation {conv['id']}")
            for text in turns:
                print(f"  user> {text[:60]}...")
                with c.stream("POST", f"/api/conversations/{conv['id']}/messages", json={"content": text}) as resp:
                    resp.raise_for_status()
                    reply = sse_final_text(resp)
                print(f"  ai  > {reply[:80].replace(chr(10), ' ')}...")
    print("\nseed done")


if __name__ == "__main__":
    main()
