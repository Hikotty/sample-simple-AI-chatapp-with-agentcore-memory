// memchat フロントエンド。フレームワークなし。
// 認証: バックエンドから受け取った Cognito ID トークンを localStorage に保持し Bearer で送る。

const $ = (id) => document.getElementById(id);
const state = { token: localStorage.getItem("memchat_token"), me: null, conversations: [], current: null, streaming: false, mode: "login" };

// ---------- API ----------
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) { logout(); throw new Error("unauthorized"); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}

// ---------- 認証 ----------
function setAuthMode(mode) {
  state.mode = mode;
  const login = mode === "login";
  $("auth-mode-label").textContent = login ? "アカウントにサインイン" : "新しいアカウントを作成";
  $("auth-submit").textContent = login ? "サインイン" : "アカウント作成";
  $("auth-toggle").textContent = login ? "アカウントを作成する" : "既存のアカウントでサインイン";
  $("password").autocomplete = login ? "current-password" : "new-password";
  $("auth-error").textContent = "";
}

async function handleAuth(e) {
  e.preventDefault();
  const email = $("email").value.trim();
  const password = $("password").value;
  $("auth-error").textContent = "";
  $("auth-submit").disabled = true;
  try {
    if (state.mode === "signup") {
      await api("/api/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) });
    }
    const { id_token } = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
    state.token = id_token;
    localStorage.setItem("memchat_token", id_token);
    await enterChat();
  } catch (err) {
    $("auth-error").textContent = err.message;
  } finally {
    $("auth-submit").disabled = false;
  }
}

function logout() {
  state.token = null; state.me = null; state.current = null; state.conversations = [];
  localStorage.removeItem("memchat_token");
  $("chat").classList.add("hidden");
  $("auth").classList.remove("hidden");
  $("password").value = "";
}

async function enterChat() {
  state.me = await api("/api/me");
  $("memory-badge").classList.toggle("hidden", !state.me.memory_enabled);
  $("auth").classList.add("hidden");
  $("chat").classList.remove("hidden");
  await loadConversations();
  if (state.conversations.length) await openConversation(state.conversations[0].id);
  // 初期ロードが終わってからユーザー名を出す（画面が操作可能になった合図にもなる）
  $("me").textContent = state.me.email;
}

// ---------- 会話一覧 ----------
async function loadConversations() {
  state.conversations = await api("/api/conversations");
  renderConversations();
}

function renderConversations() {
  const nav = $("conversations");
  nav.innerHTML = "";
  for (const c of state.conversations) {
    const item = document.createElement("div");
    item.className = "conv-item" + (state.current === c.id ? " active" : "");
    item.dataset.id = c.id;
    item.setAttribute("data-testid", "conv-item");
    const title = document.createElement("span");
    title.className = "title"; title.textContent = c.title;
    const del = document.createElement("button");
    del.className = "delete"; del.title = "削除"; del.textContent = "✕";
    del.setAttribute("data-testid", "conv-delete");
    del.addEventListener("click", (e) => { e.stopPropagation(); deleteConversation(c.id); });
    item.append(title, del);
    item.addEventListener("click", () => openConversation(c.id));
    nav.appendChild(item);
  }
}

async function newConversation() {
  if (state.streaming) return;
  // 作成 API の応答を待つ間に送信されると前の会話へ届いてしまうので、先に入力を閉じて現在の会話を外す
  state.current = null;
  setComposerEnabled(false);
  $("conv-title").textContent = "新しいチャット";
  $("messages").innerHTML = '<div class="empty">最初のメッセージを送ってみましょう。</div>';
  const c = await api("/api/conversations", { method: "POST" });
  state.conversations.unshift(c);
  await openConversation(c.id);
  $("input").focus();
}

async function deleteConversation(id) {
  if (!confirm("この会話を削除しますか？")) return;
  await api(`/api/conversations/${id}`, { method: "DELETE" });
  state.conversations = state.conversations.filter((c) => c.id !== id);
  if (state.current === id) {
    state.current = null;
    $("messages").innerHTML = '<div class="empty">左の「新しいチャット」から会話を始めてください。</div>';
    $("conv-title").textContent = "memchat";
    setComposerEnabled(false);
  }
  renderConversations();
}

async function openConversation(id) {
  if (state.streaming) return;
  state.current = id;
  const conv = state.conversations.find((c) => c.id === id);
  $("conv-title").textContent = conv ? conv.title : "memchat";
  renderConversations();
  const msgs = await api(`/api/conversations/${id}/messages`);
  // 待っている間に別の会話へ切り替わっていたら、この結果は捨てる（古い応答で画面を上書きしない）
  if (state.current !== id) return;
  const box = $("messages");
  box.innerHTML = "";
  if (!msgs.length) {
    box.innerHTML = '<div class="empty">最初のメッセージを送ってみましょう。</div>';
  }
  for (const m of msgs) appendMessage(m.role, m.content);
  setComposerEnabled(true);
  scrollToBottom();
}

// ---------- メッセージ描画 ----------
function appendMessage(role, text) {
  const empty = document.querySelector("#messages .empty");
  if (empty) empty.remove();
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  wrap.setAttribute("data-testid", `msg-${role}`);
  const avatar = document.createElement("div");
  avatar.className = "avatar"; avatar.textContent = role === "user" ? "You" : "AI";
  const body = document.createElement("div");
  body.className = "body"; body.textContent = text;
  wrap.append(avatar, body);
  $("messages").appendChild(wrap);
  return body;
}

function scrollToBottom() { const box = $("messages"); box.scrollTop = box.scrollHeight; }
function setComposerEnabled(on) { $("input").disabled = !on; $("send").disabled = !on; }

// ---------- 送信（SSE を fetch で読む） ----------
async function sendMessage(e) {
  e.preventDefault();
  const text = $("input").value.trim();
  if (!text || !state.current || state.streaming) return;
  state.streaming = true;
  setComposerEnabled(false);
  $("input").value = "";
  appendMessage("user", text);
  const body = appendMessage("assistant", "");
  body.classList.add("streaming");
  scrollToBottom();

  try {
    const res = await fetch(`/api/conversations/${state.current}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${state.token}` },
      body: JSON.stringify({ content: text }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, idx); buffer = buffer.slice(idx + 2);
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        handleEvent(JSON.parse(line.slice(6)), body);
      }
    }
  } catch (err) {
    body.textContent = `エラー: ${err.message}`;
  } finally {
    body.classList.remove("streaming");
    body.setAttribute("data-testid", "assistant-final");
    state.streaming = false;
    setComposerEnabled(true);
    await loadConversations(); // タイトル（初回メッセージから自動生成）と並び順を反映
    $("conv-title").textContent = (state.conversations.find((c) => c.id === state.current) || {}).title || "memchat";
    $("input").focus();
  }
}

function handleEvent(ev, body) {
  if (ev.type === "token") {
    body.textContent += ev.text;
    scrollToBottom();
  } else if (ev.type === "memory") {
    // 長期記憶が参照されたことを控えめに表示（検証で見えるようにするための表示）
    const note = document.createElement("div");
    note.className = "memory-note";
    note.setAttribute("data-testid", "memory-note");
    note.textContent = `長期記憶を ${ev.count} 件参照: ` + ev.items.map((s) => s.slice(0, 60)).join(" / ");
    body.parentElement.before(note);
  } else if (ev.type === "error") {
    body.textContent = ev.message;
  }
}

// ---------- 初期化 ----------
function init() {
  $("auth-form").addEventListener("submit", handleAuth);
  $("auth-toggle").addEventListener("click", () => setAuthMode(state.mode === "login" ? "signup" : "login"));
  $("logout").addEventListener("click", logout);
  $("new-chat").addEventListener("click", newConversation);
  $("composer").addEventListener("submit", sendMessage);
  $("input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $("composer").requestSubmit(); }
  });
  $("input").addEventListener("input", (e) => {
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
  });
  setAuthMode("login");
  if (state.token) {
    enterChat().catch(() => logout());
  } else {
    $("auth").classList.remove("hidden");
  }
}

document.addEventListener("DOMContentLoaded", init);
