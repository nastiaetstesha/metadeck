// metadeck/session/static/session/js/room.js
(function () {
  const sessionId = window.__SESSION_ID__;
  const debug = !!window.__DEBUG__;

  const wsStatus = document.getElementById("wsStatus");
  const grid = document.getElementById("cardsGrid");

  const btnDraw1 = document.getElementById("btnDraw1");
  const btnDraw6 = document.getElementById("btnDraw6");
  const btnReset = document.getElementById("btnReset");

  // Zoom modal
  const zoomModal = document.getElementById("zoomModal");
  const zoomImg = document.getElementById("zoomImg");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomCloseBtn = document.getElementById("zoomCloseBtn");

  let zoomScale = 1;

  const scheme = (window.location.protocol === "https:") ? "wss" : "ws";
  const wsUrl = `${scheme}://${window.location.host}/ws/s/${sessionId}/`;

  let ws = null;
  let reconnectTimer = null;

  function setWsStatus(text, ok) {
    wsStatus.textContent = text;
    wsStatus.style.color = ok ? "rgba(255,255,255,.82)" : "rgba(255,255,255,.62)";
  }

  function connect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    setWsStatus("WS: connecting...", false);

    ws = new WebSocket(wsUrl);

    ws.onopen = () => setWsStatus("WS: connected", true);

    ws.onclose = () => {
      setWsStatus("WS: disconnected", false);
      reconnectTimer = setTimeout(connect, 700);
    };

    ws.onerror = () => setWsStatus("WS: error", false);

    ws.onmessage = (event) => {
      const data = safeJson(event.data);
      if (!data) return;

      if (data.type === "state") {
        renderCards(data.cards || [], data.flips || {});
      }

      if (data.type === "flip") {
        applyFlip(data.card_id, data.flipped);
      }
    };
  }

  function safeJson(s) {
    try { return JSON.parse(s); } catch { return null; }
  }

  function send(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }

  function sendAction(action) {
    send({ action });
  }

  function esc(s) {
    return String(s || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderCards(cards, flips) {
    if (!cards.length) {
      grid.innerHTML = `
        <div class="panel empty wide">
          No cards yet. Click “Draw 1” or “Draw 6”.
        </div>
      `;
      return;
    }

    const html = cards.map((c) => {
      const flipped = !!(flips && flips[String(c.id)]);
      return `
        <div class="flip-wrap">
          <div class="flip-card ${flipped ? "is-flipped" : ""}"
               data-flip
               data-card-id="${esc(c.id)}"
               data-back="${esc(c.back_url)}"
               data-front="${esc(c.front_url)}">
            <div class="flip-face flip-front">
              ${c.back_url ? `<img src="${esc(c.back_url)}" alt="back">` : `<div class="empty">No back image</div>`}
            </div>
            <div class="flip-face flip-back">
              ${c.front_url ? `<img src="${esc(c.front_url)}" alt="card">` : `<div class="empty">No card image</div>`}
            </div>

            <button class="zoom-btn" type="button" data-zoom title="Zoom">+</button>
          </div>
          ${debug ? `
            <div class="debug">back: ${esc(c.back_url)}<br>front: ${esc(c.front_url)}</div>
          ` : ``}
        </div>
      `;
    }).join("");

    grid.innerHTML = html;
  }

  function applyFlip(cardId, flipped) {
    if (!cardId) return;
    const el = grid.querySelector(`.flip-card[data-card-id="${CSS.escape(String(cardId))}"]`);
    if (!el) return;

    if (flipped) el.classList.add("is-flipped");
    else el.classList.remove("is-flipped");
  }

  // Buttons
  btnDraw1?.addEventListener("click", () => sendAction("draw_one"));
  btnDraw6?.addEventListener("click", () => sendAction("draw_six"));
  btnReset?.addEventListener("click", () => sendAction("reset"));

  // Click handling (flip or zoom)
  document.addEventListener("click", (e) => {
    const zoomBtn = e.target.closest("[data-zoom]");
    if (zoomBtn) {
      e.preventDefault();
      e.stopPropagation();
      const card = zoomBtn.closest(".flip-card");
      if (!card) return;

      // показываем лицевую сторону если перевёрнута, иначе рубашку
      const isFlipped = card.classList.contains("is-flipped");
      const url = isFlipped ? card.dataset.front : card.dataset.back;
      if (!url) return;

      openZoom(url);
      return;
    }

    const card = e.target.closest(".flip-card[data-flip]");
    if (!card) return;

    // flip (и локально, и в WS)
    const cardId = card.dataset.cardId;
    const nextFlipped = !card.classList.contains("is-flipped");

    if (nextFlipped) card.classList.add("is-flipped");
    else card.classList.remove("is-flipped");

    send({
      action: "flip",
      card_id: String(cardId),
      flipped: nextFlipped,
    });
  });

  // Zoom modal logic
  function openZoom(url) {
    zoomScale = 1;
    zoomImg.src = url;
    zoomImg.style.transform = `scale(${zoomScale})`;

    zoomModal.classList.add("is-open");
    zoomModal.setAttribute("aria-hidden", "false");
  }

  function closeZoom() {
    zoomModal.classList.remove("is-open");
    zoomModal.setAttribute("aria-hidden", "true");
    zoomImg.src = "";
  }

  function zoomBy(delta) {
    zoomScale = Math.max(0.6, Math.min(2.5, zoomScale + delta));
    zoomImg.style.transform = `scale(${zoomScale})`;
  }

  zoomInBtn?.addEventListener("click", () => zoomBy(0.15));
  zoomOutBtn?.addEventListener("click", () => zoomBy(-0.15));
  zoomCloseBtn?.addEventListener("click", closeZoom);

  zoomModal?.addEventListener("click", (e) => {
    if (e.target === zoomModal) closeZoom();
  });

  document.addEventListener("keydown", (e) => {
    if (!zoomModal.classList.contains("is-open")) return;
    if (e.key === "Escape") closeZoom();
    if (e.key === "+" || e.key === "=") zoomBy(0.15);
    if (e.key === "-") zoomBy(-0.15);
  });

  connect();
})();
