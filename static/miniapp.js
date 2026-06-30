// Ubique Pay — Telegram Mini App: full send flow.
// auth (signed initData) → KYC → card → quote → confirm → result.

(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const API = "/api/v1";
  let token = null;
  let cards = [];
  let pendingQuote = null;

  const $ = (id) => document.getElementById(id);
  const show = (id, on = true) => $(id).classList.toggle("hidden", !on);
  function setStatus(text, ok) {
    const el = $("status");
    el.textContent = text;
    el.className = "status " + (ok === true ? "ok" : ok === false ? "bad" : "");
  }

  async function api(method, path, body) {
    const res = await fetch(API + path, {
      method,
      headers: Object.assign(
        { "Content-Type": "application/json" },
        token ? { Authorization: "Token " + token } : {}
      ),
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty */ }
    return { ok: res.ok, status: res.status, data };
  }

  // 1) Authenticate
  async function authenticate() {
    const initData = tg ? tg.initData : "";
    if (!initData) { setStatus("Open inside Telegram to sign in.", false); return; }
    const r = await api("POST", "/auth/telegram/", { init_data: initData });
    if (!r.ok) { setStatus("Sign-in failed: " + (r.data.detail || r.status), false); return; }
    token = r.data.token;
    setStatus("Signed in ✓", true);
    await refresh();
  }

  // 2) KYC gate
  async function refresh() {
    const me = await api("GET", "/auth/me/");
    const verified = me.data.kyc_status === "verified";
    show("kyc", !verified);
    show("wallet", verified);
    show("send", verified);
    if (verified) await loadWallet();
  }

  $("kyc-btn").onclick = async () => {
    $("kyc-btn").disabled = true;
    const r = await api("POST", "/auth/kyc/start/");
    const sdkToken = r.data && r.data.sdk_token;
    if (sdkToken && window.snsWebSdk) {
      launchSumsub(sdkToken);
    } else {
      await refresh(); // demo provider auto-verifies (no SDK token)
    }
  };

  function launchSumsub(token) {
    $("kyc-btn").classList.add("hidden");
    const sdk = snsWebSdk
      .init(token, () => api("POST", "/auth/kyc/token/").then((r) => r.data.token))
      .withConf({ lang: "en" })
      .on("idCheck.onApplicantStatusChanged", () => refresh())
      .on("idCheck.onApplicantSubmitted", () => setStatus("Verification submitted, reviewing…"))
      .build();
    sdk.launch("#sumsub");
  }

  // 3) Wallet / cards
  async function loadWallet() {
    const r = await api("GET", "/wallets/cards/");
    cards = r.data.results || r.data || [];
    $("cards").innerHTML = cards.length
      ? cards.map((c) => `<div class="ci">${c.brand} ····${c.last4}</div>`).join("")
      : '<div class="muted">No cards yet.</div>';
  }

  $("addcard-btn").onclick = async () => {
    await api("POST", "/wallets/cards/", { brand: "Visa", last4: "1436", provider_token: "" });
    await loadWallet();
  };

  // 4) Quote
  $("quote-btn").onclick = async () => {
    const body = {
      send_amount: $("amount").value || "0",
      send_currency: $("from-ccy").value,
      receive_currency: $("to-ccy").value,
    };
    const r = await api("POST", "/quotes/", body);
    if (!r.ok) { setStatus(r.data.detail || "Quote failed", false); return; }
    pendingQuote = body;
    const q = r.data;
    $("quote").innerHTML =
      `<div class="line"><span>You send</span><span>${q.send_amount} ${q.send_currency}</span></div>` +
      `<div class="line"><span class="muted">Fees</span><span class="muted">${q.onramp_fee} + ${q.commission} ${q.send_currency}</span></div>` +
      `<div class="line"><span>Network</span><span class="pill">${q.network}</span></div>` +
      `<div class="line"><span>Recipient gets</span><span class="big">${q.receive_amount} ${q.receive_currency}</span></div>`;
    show("quote", true);
    show("confirm-btn", true);
  };

  // 5) Confirm → create transfer
  $("confirm-btn").onclick = async () => {
    if (!cards.length) { setStatus("Add a card first.", false); return; }
    if (!$("r-last4").value) { setStatus("Enter recipient card.", false); return; }
    $("confirm-btn").disabled = true;
    const r = await api("POST", "/transfers/", {
      source_card_id: cards[0].id,
      recipient_card_last4: $("r-last4").value,
      send_amount: pendingQuote.send_amount,
      send_currency: pendingQuote.send_currency,
      receive_currency: pendingQuote.receive_currency,
      idempotency_key: (crypto.randomUUID && crypto.randomUUID()) || String(Date.now()),
    });
    $("confirm-btn").disabled = false;
    if (!r.ok) { setStatus(r.data.detail || "Transfer failed", false); return; }
    const t = r.data;
    show("send", false);
    show("result", true);
    $("result").innerHTML =
      `<h2>${t.status === "completed" ? "Sent ✓" : "Status: " + t.status}</h2>` +
      `<p class="big" style="color:var(--mint);font-size:1.3rem">${t.receive_amount} ${t.receive_currency}</p>` +
      `<p class="muted">to ····${t.recipient_card_last4} over ${t.network}` +
      (t.chain_tx ? ` · tx ${t.chain_tx}` : "") + `</p>`;
    if (tg) tg.HapticFeedback && tg.HapticFeedback.notificationOccurred("success");
  };

  // TON Connect (link a wallet)
  try {
    if (window.TON_CONNECT_UI) {
      new TON_CONNECT_UI.TonConnectUI({
        manifestUrl: location.origin + "/tonconnect-manifest.json",
        buttonRootId: "ton-connect",
      });
    }
  } catch (e) { /* ignore */ }

  if (tg) {
    tg.ready(); tg.expand();
    const u = tg.initDataUnsafe && tg.initDataUnsafe.user;
    if (u) $("who").textContent = "@" + (u.username || u.first_name || u.id);
  }
  authenticate();
})();
