// metadeck/session/static/session/js/room.js
(function () {
  const sessionId = window.__SESSION_ID__;
  const debug = !!window.__DEBUG__;

  const wsStatus = document.getElementById("wsStatus");
  const grid = document.getElementById("cardsGrid");

  const btnDraw1 = document.getElementById("btnDraw1");
  const btnDraw3 = document.getElementById("btnDraw3");
  const btnDraw6 = document.getElementById("btnDraw6");
  const btnReset = document.getElementById("btnReset");

  // Zoom modal 
  const zoomModal = document.getElementById("zoomModal");
  const zoomImg = document.getElementById("zoomImg");
  const zoomInBtn = document.getElementById("zoomInBtn");
  const zoomOutBtn = document.getElementById("zoomOutBtn");
  const zoomCloseBtn = document.getElementById("zoomCloseBtn");

//   let zoomLevel = 1;

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${scheme}://${window.location.host}/ws/s/${sessionId}/`;

  let ws = null;
  let reconnectTimer = null;

  function setWsStatus(text, ok) {
    if (!wsStatus) return;
    wsStatus.textContent = text;
    wsStatus.style.color = ok ? "rgba(255,255,255,.82)" : "rgba(255,255,255,.62)";
  }

  function safeJson(s) {
    try {
      return JSON.parse(s);
    } catch {
      return null;
    }
  }

  function send(payload) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }

  function sendAction(action) {
    send({ action });
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
      } else if (data.type === "flip") {
        applyFlip(data.card_id, data.flipped);
      }
    };
  }

  function esc(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function renderCards(cards, flips) {
    if (!grid) return;

    if (!cards.length) {
      grid.innerHTML = `
        <div class="panel empty wide">
          No cards yet. Click “Draw 1” or “Draw 6”.
        </div>
      `;
      return;
    }

    const html = cards
      .map((c) => {
        const cid = String(c.id);
        const flipped = !!flips[cid];

        return `
          <div class="flip-wrap">
            <button class="zoom-open" type="button" data-zoom title="Preview">🔍</button>

            <div class="flip-card ${flipped ? "is-flipped" : ""}"
                 data-flip
                 data-card-id="${esc(cid)}"
                 data-back="${esc(c.back_url)}"
                 data-front="${esc(c.front_url)}">

              <div class="flip-face flip-front">
                ${
                  c.back_url
                    ? `<img src="${esc(c.back_url)}" alt="back">`
                    : `<div class="empty">No back image</div>`
                }
              </div>

              <div class="flip-face flip-back">
                ${
                  c.front_url
                    ? `<img src="${esc(c.front_url)}" alt="card">`
                    : `<div class="empty">No card image</div>`
                }
              </div>
            </div>

            ${
              debug
                ? `<div class="debug">back: ${esc(c.back_url)}<br>front: ${esc(c.front_url)}</div>`
                : ``
            }
          </div>
        `;
      })
      .join("");

    grid.innerHTML = html;
  }

  function applyFlip(cardId, flipped) {
    if (!grid || cardId == null) return;
    const selector = `.flip-card[data-card-id="${CSS.escape(String(cardId))}"]`;
    const el = grid.querySelector(selector);
    if (!el) return;

    if (flipped) el.classList.add("is-flipped");
    else el.classList.remove("is-flipped");
  }

  // -------------------------
  // Zoom modal logic (ВАЖНО: zoom через реальную ширину картинки)
  // -------------------------
  let zoomLevel = 1;

function applyZoom() {
  if (!zoomModal) return;
  zoomModal.style.setProperty("--zoom", String(zoomLevel));
}

function openZoom(src) {
  if (!zoomModal || !zoomImg) return;
  if (!src) return;

  zoomLevel = 1;
  zoomImg.src = src;
  applyZoom();

  zoomModal.classList.add("is-open");
  zoomModal.setAttribute("aria-hidden", "false");

  // сброс скролла
  const body = zoomModal.querySelector(".zoom-body");
  if (body) {
    body.scrollTop = 0;
    body.scrollLeft = 0;
  }
}

function closeZoom() {
  if (!zoomModal || !zoomImg) return;

  zoomModal.classList.remove("is-open");
  zoomModal.setAttribute("aria-hidden", "true");
  zoomImg.src = "";
  zoomLevel = 1;
  applyZoom();
}

function zoomBy(delta) {
  zoomLevel = Math.max(0.6, Math.min(3.0, zoomLevel + delta));
  applyZoom();
}


  zoomCloseBtn?.addEventListener("click", closeZoom);
  zoomInBtn?.addEventListener("click", () => zoomBy(+0.15));
  zoomOutBtn?.addEventListener("click", () => zoomBy(-0.15));

  // закрытие по клику на backdrop (у тебя он с data-zoom-close)
  zoomModal?.addEventListener("click", (e) => {
    const closeEl = e.target.closest("[data-zoom-close]");
    if (closeEl) closeZoom();
  });

  document.addEventListener("keydown", (e) => {
    if (!zoomModal?.classList.contains("is-open")) return;

    if (e.key === "Escape") closeZoom();
    if (e.key === "+" || e.key === "=") zoomBy(+0.15);
    if (e.key === "-") zoomBy(-0.15);
  });

  // -------------------------
  // Buttons
  // -------------------------
  btnDraw1?.addEventListener("click", () => sendAction("draw_one"));
  btnDraw3?.addEventListener("click", () => sendAction("draw_three"));
  btnDraw6?.addEventListener("click", () => sendAction("draw_six"));
  btnReset?.addEventListener("click", () => sendAction("reset"));

  // -------------------------
  // Click handling (zoom OR flip)
  // -------------------------
  document.addEventListener("click", (e) => {
    // 1) Zoom click (лупа)
    const zoomBtn = e.target.closest("[data-zoom]");
    if (zoomBtn) {
      e.preventDefault();
      e.stopPropagation();

      const wrap = zoomBtn.closest(".flip-wrap");
      const card = wrap?.querySelector(".flip-card");
      if (!card) return;

      const isFlipped = card.classList.contains("is-flipped");
      const src = isFlipped ? card.dataset.front : card.dataset.back;

      openZoom(src);
      return;
    }

    // 2) Flip click
    const card = e.target.closest(".flip-card[data-flip]");
    if (!card) return;

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

  connect();
})();
