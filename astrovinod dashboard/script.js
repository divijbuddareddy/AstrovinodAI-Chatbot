/* AstroVinod Dashboard
 * Reads data from the bot server:
 *   GET {server}/admin/api/customers          -> list of customers
 *   GET {server}/admin/api/chats/{phone}      -> one customer's messages (oldest first)
 * Password is sent as:  Authorization: Bearer <ADMIN_PASSWORD>
 * Field names are read flexibly, so small differences in the server's JSON still work.
 */

(() => {
  "use strict";

  const REFRESH_MS = 15000;
  const STORE_KEY = "astrovinod_dashboard";

  const state = {
    base: "",
    password: "",
    demo: false,
    customers: [],
    selected: null,       // phone
    filter: "all",
    query: "",
    timer: null,
    lastChatSig: "",
  };

  const $ = (id) => document.getElementById(id);

  /* ---------------- helpers ---------------- */
  const pick = (o, ...keys) => {
    for (const k of keys) if (o && o[k] != null && o[k] !== "") return o[k];
    return "";
  };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const toDate = (v) => {
    if (!v) return null;
    if (typeof v === "number") return new Date(v < 1e12 ? v * 1000 : v);
    const d = new Date(v);
    return isNaN(d) ? null : d;
  };

  const sameDay = (a, b) => a.toDateString() === b.toDateString();
  const hhmm = (d) => d ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";

  const listTime = (d) => {
    if (!d) return "";
    const now = new Date();
    if (sameDay(d, now)) return hhmm(d);
    const y = new Date(now); y.setDate(now.getDate() - 1);
    if (sameDay(d, y)) return "Yesterday";
    return d.toLocaleDateString([], { day: "2-digit", month: "short" });
  };

  const dayLabel = (d) => {
    const now = new Date();
    if (sameDay(d, now)) return "Today";
    const y = new Date(now); y.setDate(now.getDate() - 1);
    if (sameDay(d, y)) return "Yesterday";
    return d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "long", year: "numeric" });
  };

  const initials = (name, phone) => {
    const n = String(name || "").trim();
    if (n) return n.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    return String(phone || "?").slice(-2);
  };

  const colorFor = (s) => {
    let h = 0;
    for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360;
    return `hsl(${h} 45% 38%)`;
  };

  const avatarHTML = (name, phone) =>
    `<div class="avatar" style="background:${colorFor(phone || name)}">${esc(initials(name, phone))}</div>`;

  const maskPhone = (p) => {
    const s = String(p || "");
    return s.startsWith("+") ? s : (s.length > 10 ? "+" + s : s);
  };

  function toast(msg) {
    const t = $("toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.hidden = true), 3500);
  }

  /* ---------------- normalise server data ---------------- */
  function normCustomer(c) {
    const status = String(pick(c, "status", "state", "stage", "onboarding_state")).toLowerCase();
    const registered = c.registered ?? c.is_registered ?? c.onboarded ?? c.complete;
    let tag;
    if (registered === true) tag = "active";
    else if (registered === false) tag = "onboarding";
    else tag = /onboard|regist|pending|ask|await|new/.test(status) ? "onboarding" : "active";

    return {
      phone: String(pick(c, "phone", "wa_id", "phone_number", "number", "id")),
      name: pick(c, "name", "full_name", "customer_name"),
      last: pick(c, "last_message", "last_text", "lastMessage", "preview"),
      lastWho: pick(c, "last_role", "last_sender", "last_direction"),
      time: toDate(pick(c, "last_time", "last_message_at", "updated_at", "lastTime", "created_at")),
      tag,
      dob: pick(c, "dob", "date_of_birth", "birth_date"),
      tob: pick(c, "tob", "time_of_birth", "birth_time"),
      place: pick(c, "place", "birth_place", "place_of_birth", "birthplace"),
      lagna: pick(c, "lagna", "ascendant"),
      moon: pick(c, "moon_sign", "rashi", "moon"),
      nakshatra: pick(c, "nakshatra", "star"),
      joined: toDate(pick(c, "created_at", "joined_at", "first_seen")),
      count: pick(c, "message_count", "messages", "count"),
    };
  }

  function normMessage(m) {
    const role = String(pick(m, "role", "sender", "direction", "from", "who")).toLowerCase();
    const fromBot = /bot|assistant|out|system|astro|model/.test(role);
    return {
      bot: fromBot,
      text: String(pick(m, "text", "message", "content", "body")),
      time: toDate(pick(m, "time", "created_at", "timestamp", "sent_at")),
    };
  }

  /* ---------------- API ---------------- */
  async function api(path) {
    if (state.demo) return Demo.get(path);
    const res = await fetch(state.base.replace(/\/+$/, "") + path, {
      headers: { Authorization: "Bearer " + state.password, Accept: "application/json" },
      cache: "no-store",
    });
    if (res.status === 401 || res.status === 403) throw new Error("Wrong password");
    if (res.status === 404) throw new Error("Dashboard API not found on the server (" + path.split("?")[0] + ")");
    if (!res.ok) throw new Error("Server error " + res.status);
    return res.json();
  }

  const asArray = (d, ...keys) => {
    if (Array.isArray(d)) return d;
    for (const k of keys) if (Array.isArray(d?.[k])) return d[k];
    return [];
  };

  async function loadCustomers() {
    const data = await api("/admin/api/customers");
    state.customers = asArray(data, "customers", "data", "items")
      .map(normCustomer)
      .filter((c) => c.phone)
      .sort((a, b) => (b.time?.getTime() || 0) - (a.time?.getTime() || 0));
    renderStats();
    renderList();
    setLive(true);
  }

  async function loadChat(phone, keepScroll) {
    const data = await api("/admin/api/chats/" + encodeURIComponent(phone));
    if (state.selected !== phone) return;
    const msgs = asArray(data, "messages", "chats", "data", "items").map(normMessage)
      .sort((a, b) => (a.time?.getTime() || 0) - (b.time?.getTime() || 0));
    const sig = msgs.length + "|" + (msgs.at(-1)?.text || "");
    if (keepScroll && sig === state.lastChatSig) return; // nothing new
    state.lastChatSig = sig;
    renderMessages(msgs, keepScroll);
  }

  /* ---------------- rendering ---------------- */
  function renderStats() {
    const cs = state.customers;
    const today = new Date();
    const activeToday = cs.filter((c) => c.time && sameDay(c.time, today)).length;
    const setUp = cs.filter((c) => c.tag === "active").length;
    $("stats").innerHTML = `
      <div class="stat"><b>${cs.length}</b><span>Customers</span></div>
      <div class="stat"><b>${activeToday}</b><span>Chatted today</span></div>
      <div class="stat"><b>${setUp}</b><span>Set up</span></div>`;
  }

  function renderList() {
    const q = state.query.trim().toLowerCase();
    const list = state.customers.filter((c) =>
      (state.filter === "all" || c.tag === state.filter) &&
      (!q || c.name.toLowerCase().includes(q) || c.phone.includes(q.replace(/\D/g, "") || q)));

    const ul = $("customerList");
    if (!list.length) {
      ul.innerHTML = `<li class="list-empty">${state.customers.length ? "No customers match." : "No customers yet."}</li>`;
      return;
    }
    ul.innerHTML = list.map((c) => `
      <li class="customer ${c.phone === state.selected ? "selected" : ""}" data-phone="${esc(c.phone)}">
        ${avatarHTML(c.name, c.phone)}
        <div class="info">
          <div class="row">
            <span class="name">${esc(c.name || maskPhone(c.phone))}</span>
            <span class="time">${esc(listTime(c.time))}</span>
          </div>
          <div class="row">
            <span class="last">${/bot|assistant/.test(String(c.lastWho).toLowerCase()) ? '<span class="tk">✓✓</span>' : ""}${esc(c.last || "—")}</span>
            <span class="tag ${c.tag}">${c.tag === "active" ? "set up" : "registering"}</span>
          </div>
        </div>
      </li>`).join("");
  }

  function renderMessages(msgs, keepScroll) {
    const box = $("messages");
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
    if (!msgs.length) {
      box.innerHTML = `<div class="empty">No messages yet.</div>`;
      return;
    }
    let html = "", lastDay = null, prevBot = null;
    for (const m of msgs) {
      if (m.time && (!lastDay || !sameDay(m.time, lastDay))) {
        html += `<div class="day">${esc(dayLabel(m.time))}</div>`;
        lastDay = m.time;
        prevBot = null;
      }
      const first = prevBot !== m.bot;
      prevBot = m.bot;
      const isFile = /^\[(document|image|photo|audio|video|file|sticker|unsupported)[^\]]*\]$/i.test(m.text.trim());
      html += `<div class="bubble ${m.bot ? "out" : "in"}${first ? " first" : ""}"><span class="${isFile ? "file" : ""}">${isFile ? "📎 " : ""}${esc(m.text)}</span><span class="meta">${esc(hhmm(m.time))}${m.bot ? '<span class="tk">✓✓</span>' : ""}</span></div>`;
    }
    box.innerHTML = html;
    if (!keepScroll || atBottom) box.scrollTop = box.scrollHeight;
  }

  function renderProfile() {
    const c = current();
    if (!c) { $("profileBody").innerHTML = ""; return; }
    const f = (label, v) => `<div class="field"><span>${label}</span><b>${esc(v || "—")}</b></div>`;
    const digits = c.phone.replace(/\D/g, "");
    $("profileBody").innerHTML = `
      <div class="profile-top">
        ${avatarHTML(c.name, c.phone)}
        <h2>${esc(c.name || "Unknown")}</h2>
        <div class="muted">${esc(maskPhone(c.phone))}</div>
        <div style="margin-top:10px"><span class="tag ${c.tag}">${c.tag === "active" ? "set up" : "still registering"}</span></div>
      </div>
      <div class="fields">
      ${f("Date of birth", c.dob)}
      ${f("Time of birth", c.tob)}
      ${f("Place of birth", c.place)}
      ${f("Lagna (Ascendant)", c.lagna)}
      ${f("Moon sign (Rashi)", c.moon)}
      ${f("Nakshatra", c.nakshatra)}
      ${f("First message", c.joined ? c.joined.toLocaleString() : "")}
      ${c.count !== "" ? f("Messages", c.count) : ""}
      </div>
      ${digits ? `<a class="wa-link" href="https://wa.me/${digits}" target="_blank" rel="noopener">Open in WhatsApp ↗</a>` : ""}`;
  }

  const current = () => state.customers.find((c) => c.phone === state.selected);

  /* ---------------- actions ---------------- */
  async function selectCustomer(phone) {
    state.selected = phone;
    state.lastChatSig = "";
    const c = current();
    $("chatAvatar").outerHTML = `<div class="avatar" id="chatAvatar" style="background:${colorFor(phone)}">${esc(initials(c?.name, phone))}</div>`;
    $("chatName").textContent = c?.name || maskPhone(phone);
    $("chatPhone").textContent = maskPhone(phone);
    $("profileBtn").disabled = false;
    $("messages").innerHTML = `<div class="empty">Loading…</div>`;
    $("app").classList.add("view-chat");
    renderList();
    renderProfile();
    try { await loadChat(phone, false); }
    catch (e) { $("messages").innerHTML = `<div class="empty">Could not load chat: ${esc(e.message)}</div>`; }
  }

  async function refresh(silent) {
    try {
      await loadCustomers();
      if (state.selected) { renderProfile(); await loadChat(state.selected, true); }
    } catch (e) {
      setLive(false);
      if (!silent) toast(e.message);
      if (!state.customers.length) {
        const why = e.message === "Failed to fetch"
          ? "Can't reach the server (it may be waking up, retrying every 15 s)."
          : e.message;
        $("customerList").innerHTML = `<li class="list-empty">⚠️ ${esc(why)}</li>`;
      }
    }
  }

  function setLive(ok) { $("liveDot").classList.toggle("off", !ok); }

  function startTimer() {
    stopTimer();
    state.timer = setInterval(() => { if (!document.hidden) refresh(true); }, REFRESH_MS);
  }
  function stopTimer() { clearInterval(state.timer); state.timer = null; }

  async function enter() {
    $("login").hidden = true;
    $("app").hidden = false;
    $("customerList").innerHTML = `<li class="list-empty">Loading…</li>`;
    await refresh(false);
    startTimer();
  }

  function logout() {
    stopTimer();
    try { localStorage.removeItem(STORE_KEY); } catch (_) {}
    Object.assign(state, { password: "", demo: false, customers: [], selected: null });
    $("password").value = "";
    $("app").hidden = true;
    $("app").className = "app";
    $("login").hidden = false;
  }

  /* ---------------- events ---------------- */
  $("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("loginError");
    err.hidden = true;
    state.base = $("apiBase").value.trim();
    state.password = $("password").value;
    state.demo = false;
    if (!state.base || !state.password) {
      err.textContent = "Enter the server address and password.";
      err.hidden = false;
      return;
    }
    try {
      await api("/admin/api/customers"); // check before entering
    } catch (ex) {
      err.textContent = ex.message === "Failed to fetch"
        ? "Could not reach the server. Check the address, or the server is waking up (try again in 30 s)."
        : ex.message;
      err.hidden = false;
      return;
    }
    try {
      if ($("remember").checked)
        localStorage.setItem(STORE_KEY, JSON.stringify({ base: state.base, password: state.password }));
      else localStorage.removeItem(STORE_KEY);
    } catch (_) {}
    enter();
  });

  $("demoBtn").addEventListener("click", () => { state.demo = true; enter(); });
  $("logoutBtn").addEventListener("click", logout);
  $("refreshBtn").addEventListener("click", () => refresh(false));

  $("customerList").addEventListener("click", (e) => {
    const li = e.target.closest(".customer");
    if (li) selectCustomer(li.dataset.phone);
  });

  $("search").addEventListener("input", (e) => { state.query = e.target.value; renderList(); });

  document.querySelectorAll(".chip").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".chip").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.filter = b.dataset.filter;
    renderList();
  }));

  $("profileBtn").addEventListener("click", () => $("app").classList.toggle("show-profile"));
  document.querySelector(".chat-title").addEventListener("click", () => {
    if (state.selected) $("app").classList.add("show-profile");
  });
  $("closeProfile").addEventListener("click", () => $("app").classList.remove("show-profile"));
  $("backBtn").addEventListener("click", () => $("app").classList.remove("view-chat", "show-profile"));

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && !$("app").hidden) refresh(true);
  });

  /* ---------------- demo data ---------------- */
  const Demo = (() => {
    const now = Date.now(), min = 60e3, day = 864e5;
    const customers = [
      { phone: "919812345670", name: "Ravi Kumar", status: "active", dob: "14-08-1992", tob: "06:45 AM", place: "Hyderabad, Telangana",
        lagna: "Leo", moon_sign: "Capricorn", nakshatra: "Shravana", created_at: now - 6 * day },
      { phone: "919900112233", name: "Priya S.", status: "active", dob: "02-03-1995", tob: "11:20 PM", place: "Chennai, Tamil Nadu",
        lagna: "Scorpio", moon_sign: "Taurus", nakshatra: "Rohini", created_at: now - 3 * day },
      { phone: "918712340000", name: "", status: "onboarding", created_at: now - day },
      { phone: "919845001122", name: "Anil Reddy", status: "active", dob: "21-11-1988", tob: "03:10 PM", place: "Vijayawada, Andhra Pradesh",
        lagna: "Aries", moon_sign: "Sagittarius", nakshatra: "Moola", created_at: now - 10 * day },
    ];
    const chats = {
      "919812345670": [
        ["user", "Hi", now - 2 * day], ["bot", "🙏 Namaste! Welcome to AstroVinod. What is your full name?", now - 2 * day + min],
        ["user", "Ravi Kumar", now - 2 * day + 2 * min], ["bot", "Thank you Ravi ji. Please share your date of birth (DD-MM-YYYY).", now - 2 * day + 3 * min],
        ["user", "When will I get a job?", now - 30 * min],
        ["bot", "🙏 Namaste Ravi ji.\n\nSaturn in your 10th house is now supporting career. The period from next month looks favourable for interviews — focus on applications in the second half of the month.", now - 29 * min],
      ],
      "919900112233": [
        ["user", "Daily guidance please", now - day - 3 * 60 * min],
        ["bot", "🌅 Today's guidance for Priya ji:\nMoon transits your 5th house — a good day for learning and creative work. Lucky colour: white.", now - day - 3 * 60 * min + min],
        ["user", "[document: kundli.pdf]", now - day - 2 * 60 * min],
        ["bot", "Thank you, I have noted your kundli details.", now - day - 2 * 60 * min + min],
      ],
      "918712340000": [
        ["user", "Hello", now - 3 * 60 * min], ["bot", "🙏 Namaste! Welcome to AstroVinod. What is your full name?", now - 3 * 60 * min + min],
      ],
      "919845001122": [
        ["user", "Is this a good week to buy a house?", now - 4 * day],
        ["bot", "Anil ji, Jupiter aspecting your 4th house makes property matters favourable this week, especially Thursday.", now - 4 * day + min],
      ],
    };
    return {
      async get(path) {
        await new Promise((r) => setTimeout(r, 150));
        if (path.startsWith("/admin/api/customers")) {
          return customers.map((c) => {
            const m = chats[c.phone] || [];
            const last = m.at(-1);
            return { ...c, last_message: last?.[1], last_time: last?.[2], message_count: m.length };
          });
        }
        const phone = decodeURIComponent(path.split("/").pop());
        return (chats[phone] || []).map(([role, text, time]) => ({ role, text, time }));
      },
    };
  })();

  /* ---------------- start ---------------- */
  // Login is always asked. config.js (this computer only) just fills in the server address.
  const cfg = window.ASTRO_CONFIG;
  if (cfg?.server) {
    $("apiBase").value = cfg.server;
    $("apiBase").closest("label").hidden = true;
  }
  if (location.hash) history.replaceState(null, "", location.pathname); // old #key= links no longer log in
  // Opened as a file without config.js: sample-data demo.
  if (location.protocol === "file:" && !cfg?.server) {
    state.demo = true;
    $("logoutBtn").hidden = true;
    enter();
    return;
  }
  // Opened from the bot server itself (…/admin/): the server address is this site.
  if (location.protocol.startsWith("http") && location.pathname.startsWith("/admin")) {
    $("apiBase").value = location.origin;
    $("apiBase").closest("label").hidden = true;
  }
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_KEY) || "null");
    if (saved?.base && saved?.password) {
      state.base = saved.base;
      state.password = saved.password;
      $("apiBase").value = saved.base;
      enter();
    }
  } catch (_) {}
})();
