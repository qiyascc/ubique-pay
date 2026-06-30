// Ubique Pay — Telegram Mini App client.
// Authenticates the Telegram user against the backend using the *real*
// signed initData, then wires a TON Connect button so the user can link a
// TON wallet (for USDT payouts/top-ups).

(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  const statusEl = document.getElementById("status");
  const userEl = document.getElementById("tg-user");

  function setStatus(text, ok) {
    statusEl.textContent = text;
    statusEl.className = "status " + (ok ? "ok" : "bad");
  }

  if (tg) {
    tg.ready();
    tg.expand();
    if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
      const u = tg.initDataUnsafe.user;
      userEl.textContent = "@" + (u.username || u.first_name || u.id);
    }
  }

  async function authenticate() {
    const initData = tg ? tg.initData : "";
    if (!initData) {
      setStatus("Open this page inside Telegram to sign in.", false);
      return;
    }
    try {
      const res = await fetch("/api/v1/auth/telegram/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ init_data: initData }),
      });
      const data = await res.json();
      if (res.ok) {
        window.UBQ_TOKEN = data.token;
        setStatus("Signed in ✓  KYC: " + data.kyc_status, true);
      } else {
        setStatus("Sign-in failed: " + (data.detail || res.status), false);
      }
    } catch (e) {
      setStatus("Network error.", false);
    }
  }

  authenticate();

  // TON Connect — link a TON wallet.
  try {
    if (window.TON_CONNECT_UI) {
      // eslint-disable-next-line no-new
      new TON_CONNECT_UI.TonConnectUI({
        manifestUrl: location.origin + "/tonconnect-manifest.json",
        buttonRootId: "ton-connect",
      });
    }
  } catch (e) {
    console.warn("TON Connect init failed", e);
  }
})();
