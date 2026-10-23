const app = document.querySelector("#app"),
  dialog = document.querySelector("#dialog"),
  form = document.querySelector("#form");
let token = sessionStorage.getItem("kitty_token"),
  me = null,
  page = 1,
  search = "",
  status = "";
const e = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const fieldNames = {
  name: "Имя",
  username: "Логин",
  password: "Пароль",
  birth_year: "Год рождения",
  color: "Окрас",
  sitter: "Помощник",
  ends_at: "Окончание",
  starts_at: "Начало",
  due_at: "Срок",
  evidence: "Фото",
  task: "Задача",
  status: "Состояние",
  cat: "Кот",
  note: "Комментарий",
  reason: "Причина",
  non_field_errors: "",
  detail: "",
};
const colors = {
  ginger: "Рыжий",
  white: "Белый",
  black: "Чёрный",
  gray: "Серый",
  brown: "Коричневый",
  mixed: "Смешанный",
};
const labels = {
  draft: "Ожидает принятия",
  active: "В работе",
  closed: "Закрыта",
  cancelled: "Отменена",
  pending: "На проверке",
  approved: "Принято",
  rejected: "На доработке",
};
const tag = (s) =>
  `<span class="tag status-${e(s)}">${e(labels[s] || s)}</span>`;
const date = (s) =>
  new Date(s).toLocaleString("ru-RU", {
    dateStyle: "short",
    timeStyle: "short",
  });
const button = (label, action, cls = "") =>
  `<button class="${cls}" data-action="${e(action)}">${e(label)}</button>`;
async function api(path, method = "GET", body = null) {
  const headers = {};
  if (token) headers.Authorization = "Token " + token;
  if (body && !(body instanceof FormData))
    headers["Content-Type"] = "application/json";
  let r = await fetch(path, {
    method,
    headers,
    body: body
      ? body instanceof FormData
        ? body
        : JSON.stringify(body)
      : null,
  });
  if (r.status === 204) return null;
  const type = r.headers.get("content-type") || "";
  let data = type.includes("json") ? await r.json() : await r.text();
  if (!r.ok) {
    if (r.status === 401 && token) {
      token = null;
      sessionStorage.removeItem("kitty_token");
    }
    throw Error(
      typeof data === "string"
        ? data
        : Object.entries(data)
            .map(
              ([k, v]) =>
                `${["detail", "non_field_errors"].includes(k) ? "" : (fieldNames[k] || k) + ": "}${Array.isArray(v) ? v.join(" ") : v}`,
            )
            .join("\n"),
    );
  }
  return data;
}
function field(name, label, type = "text", value = "", extra = "") {
  return `<label>${e(label)}<input name="${name}" type="${type}" value="${e(value)}" ${extra}></label>`;
}
function area(name, label, value = "") {
  return `<label>${e(label)}<textarea name="${name}" maxlength="2000">${e(value)}</textarea></label>`;
}
function check(name, label, value = false) {
  return `<label><input type="checkbox" name="${name}" ${value ? "checked" : ""}>${e(label)}</label>`;
}
function select(name, label, items, value = "") {
  return `<label>${e(label)}<select name="${name}">${items.map((x) => `<option value="${e(x[0])}" ${String(x[0]) === String(value) ? "selected" : ""}>${e(x[1])}</option>`).join("")}</select></label>`;
}
function modal(title, fields, submit) {
  document.querySelector("#form-title").textContent = title;
  document.querySelector("#fields").innerHTML = fields;
  document.querySelector("#form-error").textContent = "";
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const b = form.querySelector("[type=submit]");
    b.disabled = true;
    try {
      await submit(new FormData(form));
      dialog.close();
      await render();
    } catch (err) {
      document.querySelector("#form-error").textContent = err.message;
    } finally {
      b.disabled = false;
    }
  };
  dialog.showModal();
}
document.querySelector("#cancel").onclick = () => dialog.close();
async function auth(register = false) {
  document.querySelector("#nav").hidden = true;
  app.innerHTML = `<div class="auth"><section><div class="eyebrow">Когда заботу нужно передать</div><h1>У каждого кота<br>есть свой план.</h1><p>Договоритесь об уходе, получите фотоотчёт и проверьте результат. Все задачи и решения останутся в одной смене.</p><div class="stats"><div>План ухода</div><div>Проверка</div><div>История</div></div></section><form id="auth-form"><div class="tabs">${button("Вход", "login", register ? "quiet" : "")}${button("Регистрация", "register", register ? "" : "quiet")}</div><h2>${register ? "Создать аккаунт" : "С возвращением"}</h2>${field("username", "Логин", "text", "", "required autocomplete=username maxlength=150")}${field("password", "Пароль", "password", "", "required minlength=8 autocomplete=" + (register ? "new-password" : "current-password"))}<p class="error" id="auth-error"></p><button type="submit">${register ? "Зарегистрироваться" : "Войти"}</button></form></div>`;
  app.querySelectorAll(".tabs button").forEach((b) => {
    b.type = "button";
    b.onclick = () => auth(b.dataset.action === "register");
  });
  app.querySelector("#auth-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const data = Object.fromEntries(new FormData(ev.target));
    const b = ev.target.querySelector("[type=submit]");
    b.disabled = true;
    try {
      if (register) await api("/api/users/", "POST", data);
      token = (await api("/api/token/login/", "POST", data)).auth_token;
      sessionStorage.setItem("kitty_token", token);
      me = await api("/api/users/me/");
      await render();
    } catch (err) {
      document.querySelector("#auth-error").textContent = err.message;
    } finally {
      b.disabled = false;
    }
  };
}
async function cats() {
  const data = await api(
    `/api/cats/?page=${page}&search=${encodeURIComponent(search)}&ordering=-id`,
  );
  app.innerHTML = `<div class="top"><div class="heading"><div class="eyebrow">Мои питомцы и коты сообщества</div><h1>Знакомьтесь с котами</h1><p>Вы вошли как ${e(me.username)}. Изменять карточку может её хозяин.</p></div>${button("Добавить кота", "new-cat")}</div><form class="filters" id="search"><input aria-label="Поиск по имени" name="q" placeholder="Найти кота по имени" value="${e(search)}"><button>Найти</button></form><div class="grid">${data.results.map((c) => `<article class="card">${c.image ? `<img class="cat-image" src="${e(c.image)}" alt="${e(c.name)}">` : '<div class="placeholder" aria-hidden="true">🐈</div>'}<div class="card-body"><span class="tag">${e(colors[c.color] || c.color)}</span><h2>${e(c.name)}</h2><p>${e(c.birth_year)} г. · ${c.owner === me.id ? "Ваш кот" : "Кот участника"}</p>${c.achievements.length ? `<p class="muted">Достижений: ${c.achievements.length}</p>` : ""}${c.owner === me.id ? `<div class="actions">${button("Изменить", "edit-cat:" + c.id, "quiet")}${button("Удалить", "delete-cat:" + c.id, "quiet")}</div>` : ""}</div></article>`).join("") || '<p class="empty">Котов пока нет. Добавьте первого питомца.</p>'}</div><div class="pagination">${data.previous ? button("← Назад", "prev", "quiet") : ""}<span>Страница ${page}</span>${data.next ? button("Далее →", "next", "quiet") : ""}</div>`;
  app.querySelector("#search").onsubmit = (ev) => {
    ev.preventDefault();
    search = new FormData(ev.target).get("q");
    page = 1;
    render();
  };
  bind();
}
async function catForm(id) {
  const c = id ? await api("/api/cats/" + id + "/") : {};
  let achievements = await all("/api/achievements/");
  modal(
    id ? "Изменить карточку" : "Новый кот",
    field("name", "Имя", "text", c.name || "", "required maxlength=100") +
      field(
        "birth_year",
        "Год рождения",
        "number",
        c.birth_year || new Date().getFullYear(),
        "required min=1900 max=" + new Date().getFullYear(),
      ) +
      field(
        "color",
        "Окрас",
        "text",
        c.color || "ginger",
        "required maxlength=32",
      ) +
      field("image", "Фотография", "file", "", "accept=image/*") +
      `<fieldset><legend>Достижения</legend>${achievements.map((a) => check("achievement_" + a.id, a.name, (c.achievements || []).includes(a.id))).join("")}${field("new_achievement", "Новое достижение", "text", "", "maxlength=100")}</fieldset>`,
    async (fd) => {
      const selected = achievements
        .filter((a) => fd.has("achievement_" + a.id))
        .map((a) => a.id);
      if (fd.get("new_achievement").trim()) {
        let name = fd.get("new_achievement").trim();
        let a =
          achievements.find((a) => a.name === name) ||
          (await api("/api/achievements/", "POST", { name }));
        selected.push(a.id);
      }
      const out = new FormData();
      for (const k of ["name", "birth_year", "color"]) out.set(k, fd.get(k));
      const img = fd.get("image");
      if (img.size) out.set("image", img);
      selected.forEach((v) => out.append("achievements", v));
      if (!selected.length && id) {
        await api("/api/cats/" + id + "/", "PATCH", { achievements: [] });
      }
      await api(
        "/api/cats/" + (id ? id + "/" : ""),
        id ? "PATCH" : "POST",
        out,
      );
    },
  );
}
async function all(url) {
  let rows = [];
  do {
    const d = await api(url);
    rows.push(...d.results);
    url = d.next
      ? new URL(d.next, location.origin).pathname +
        new URL(d.next, location.origin).search
      : null;
  } while (url);
  return rows;
}
async function handovers() {
  const d = await api(
    "/api/handovers/?page=" + page + (status ? "&status=" + status : ""),
  );
  const names = Object.fromEntries(
    (await all("/api/cats/")).map((c) => [c.id, c.name]),
  );
  app.innerHTML = `<div class="top"><div><div class="eyebrow">Договорённости без потерянных сообщений</div><h1>Смены ухода</h1><p>Здесь только смены, в которых вы хозяин или помощник.</p></div>${button("Передать уход", "new-handover")}</div><div class="filters">${select("status", "Состояние", [["", "Все смены"], ...Object.entries(labels).slice(0, 4)], status)}</div><div class="grid">${d.results.map((h) => `<article class="card"><div class="card-body">${tag(h.status)}<h2>${e(names[h.cat] || "Кот #" + h.cat)}</h2><p>Помощник: ${e(h.sitter)}<br>${h.owner === me.id ? "Вы — хозяин" : "Вы — помощник"}</p><p><time>${date(h.starts_at)} — ${date(h.ends_at)}</time></p><p class="note">${e(h.instructions)}</p><a class="button" href="#handover/${h.id}">Открыть смену →</a></div></article>`).join("") || '<p class="empty">Смен пока нет. Хозяин может создать план ухода и назначить помощника.</p>'}</div><div class="pagination">${d.previous ? button("← Назад", "prev", "quiet") : ""}<span>Страница ${page}</span>${d.next ? button("Далее →", "next", "quiet") : ""}</div>`;
  app.querySelector("[name=status]").onchange = (ev) => {
    status = ev.target.value;
    page = 1;
    render();
  };
  bind();
}
async function newHandover() {
  const cats = await all("/api/cats/?owner=" + me.id);
  if (!cats.length) throw Error("Сначала добавьте своего кота.");
  modal(
    "Передать уход",
    select(
      "cat",
      "Ваш кот",
      cats.map((c) => [c.id, c.name]),
    ) +
      field("sitter", "Логин помощника", "text", "", "required") +
      field("starts_at", "Начало", "datetime-local", "", "required") +
      field("ends_at", "Окончание", "datetime-local", "", "required") +
      area("instructions", "Что нужно знать об уходе"),
    async (fd) => {
      const d = Object.fromEntries(fd);
      for (const k of ["starts_at", "ends_at"])
        d[k] = new Date(d[k]).toISOString();
      const h = await api("/api/handovers/", "POST", d);
      location.hash = "handover/" + h.id;
    },
  );
}
let current = null;
async function detail(id) {
  const h = await api(`/api/handovers/${id}/`),
    tasks = await all("/api/tasks/?handover=" + id),
    incident = await all("/api/incidents/?handover=" + id),
    results = (await all("/api/completions/")).filter((r) =>
      tasks.some((t) => t.id === r.task),
    ),
    r = await api(`/api/handovers/${id}/report/`),
    ev = await all(`/api/handovers/${id}/events/`);
  current = { h, tasks, incident, results };
  let owner = h.owner === me.id;
  app.innerHTML = `<a href="#handovers">← Все смены</a><div class="top"><div><h1>Смена № ${h.id}</h1>${tag(h.status)} <span class="muted">${owner ? "Вы хозяин" : "Вы помощник"} · помощник ${e(h.sitter)}</span><p>${date(h.starts_at)} — ${date(h.ends_at)}</p></div><div class="actions">${h.status === "draft" && !owner ? button("Принять смену", "accept") : ""}${h.status === "active" && owner ? button("Закрыть смену", "close") : ""}${["active", "draft"].includes(h.status) && owner ? button("Продлить", "extend", "quiet") + button("Отменить", "cancel-handover", "quiet") : ""}</div></div><p class="note">${e(h.instructions) || "Дополнительных инструкций нет."}</p><div class="stats"><div><b>${r.approved_required}/${r.required_total}</b>обязательных принято</div><div><b>${r.overdue}</b>просрочено</div><div><b>${r.pending_reviews}</b>на проверке</div><div><b>${r.unresolved_incidents}</b>проблем не решено</div></div><p class="muted">${r.can_close ? "Все обязательные задачи приняты, открытых проблем нет — смену можно закрыть." : "Для закрытия нужны принятые обязательные задачи и решения всех проблем."}</p><section class="panel"><div class="top"><h2>План ухода</h2>${h.status === "draft" && owner ? button("Добавить задачу", "new-task") : ""}</div>${
    tasks
      .map((t) => {
        let attempts = results.filter((x) => x.task === t.id);
        return `<article class="row task ${attempts.some((x) => x.status === "approved") ? "done" : ""}"><h3>${e(t.title)}</h3><span class="tag">${t.required ? "Обязательная" : "Необязательная"}</span> ${t.photo_required ? '<span class="tag">Нужно фото</span>' : ""}<p>Срок: ${date(t.due_at)}</p><p class="note">${e(t.instructions)}</p>${attempts.map((a) => `<div class="panel">${tag(a.status)} <time>${date(a.created_at)}</time><p class="note">${e(a.note)}</p>${a.evidence_url ? button("Открыть фото", "photo:" + a.id, "quiet") : ""}${a.review_note ? `<p class="note">Ответ хозяина: ${e(a.review_note)}</p>` : ""}${owner && h.status === "active" && a.status === "pending" ? `<div class="actions">${button("Принять", "approve:" + a.id)}${button("Вернуть", "reject:" + a.id, "quiet")}</div>` : ""}</div>`).join("")}<div class="actions">${h.status === "draft" && owner ? button("Изменить", "edit-task:" + t.id, "quiet") + button("Удалить", "delete-task:" + t.id, "quiet") : ""}${h.status === "active" && !owner && !attempts.some((a) => ["pending", "approved"].includes(a.status)) ? button("Отправить результат", "submit:" + t.id) : ""}</div></article>`;
      })
      .join("") ||
    "<p>Добавьте хотя бы одну обязательную задачу перед принятием смены.</p>"
  }</section><section class="panel"><div class="top"><h2>Проблемы и решения</h2>${h.status === "active" ? button("Сообщить о проблеме", "incident") : ""}</div>${incident.map((i) => `<div class="row"><span class="tag">${i.resolved_at ? "Решена" : i.severity === "urgent" ? "Срочная" : "Открыта"}</span><p class="note">${e(i.description)}</p>${i.resolved_at ? `<p class="note">Решение: ${e(i.resolution)}</p>` : owner && h.status === "active" ? button("Записать решение", "resolve:" + i.id, "quiet") : ""}</div>`).join("") || "<p>О проблемах пока не сообщали.</p>"}</section><section class="panel"><h2>История действий</h2>${ev.map((x) => `<div class="row"><time>${date(x.created_at)}</time> · ${e({ created: "Смена создана", accepted: "Смена принята", closed: "Смена закрыта", cancelled: "Смена отменена", extended: "Смена продлена", task_created: "Задача добавлена", task_updated: "Задача изменена", task_deleted: "Задача удалена", submitted: "Результат отправлен", reviewed: "Результат проверен", incident_created: "Проблема зарегистрирована", incident_resolved: "Решение записано" }[x.kind] || x.kind)}${x.detail.reason ? "<p>" + e(x.detail.reason) + "</p>" : ""}</div>`).join("")}</section>`;
  bind();
}
function bind() {
  app.querySelectorAll("[data-action]").forEach(
    (b) =>
      (b.onclick = async () => {
        b.disabled = true;
        try {
          await act(b.dataset.action);
        } catch (err) {
          modal(
            "Действие не выполнено",
            `<p class="error">${e(err.message)}</p>`,
            async () => {},
          );
        } finally {
          b.disabled = false;
        }
      }),
  );
}
async function act(action) {
  let [a, id] = action.split(":");
  if (a === "prev" || a === "next") {
    page += a === "prev" ? -1 : 1;
    return render();
  }
  if (a === "new-cat" || a === "edit-cat") return catForm(id);
  if (a === "delete-cat")
    return modal(
      "Удалить кота",
      "<p>Карточка будет удалена. Если у кота есть смены ухода, история не даст удалить запись.</p>",
      () => api("/api/cats/" + id + "/", "DELETE"),
    );
  if (a === "new-handover") return newHandover();
  const { h, tasks } = current || {};
  const post = (path, data = {}) => api(path, "POST", data);
  const base = "/api/handovers/" + h?.id + "/";
  if (a === "accept" || a === "close") {
    await post(base + a + "/");
    return render();
  }
  if (a === "cancel-handover")
    return modal(
      "Отменить смену",
      area("reason", "Почему смена отменяется"),
      (fd) => post(base + "cancel/", Object.fromEntries(fd)),
    );
  if (a === "extend")
    return modal(
      "Продлить уход",
      field("ends_at", "Новый срок", "datetime-local", "", "required") +
        area("reason", "Причина продления"),
      (fd) =>
        post(base + "extend/", {
          ends_at: new Date(fd.get("ends_at")).toISOString(),
          reason: fd.get("reason"),
        }),
    );
  if (a === "new-task" || a === "edit-task") {
    const t = tasks.find((t) => t.id == id) || {};
    const local = t.due_at
      ? new Date(
          new Date(t.due_at) - new Date(t.due_at).getTimezoneOffset() * 60000,
        )
          .toISOString()
          .slice(0, 16)
      : "";
    return modal(
      id ? "Изменить задачу" : "Новая задача",
      field(
        "title",
        "Что сделать",
        "text",
        t.title || "",
        "required maxlength=160",
      ) +
        area("instructions", "Как выполнить", t.instructions || "") +
        field("due_at", "Срок", "datetime-local", local, "required") +
        check("required", "Обязательна для закрытия", t.required ?? true) +
        check("photo_required", "Нужен фотоотчёт", t.photo_required),
      (fd) =>
        api("/api/tasks/" + (id ? id + "/" : ""), id ? "PATCH" : "POST", {
          title: fd.get("title"),
          instructions: fd.get("instructions"),
          due_at: new Date(fd.get("due_at")).toISOString(),
          required: fd.has("required"),
          photo_required: fd.has("photo_required"),
          handover: h.id,
        }),
    );
  }
  if (a === "delete-task")
    return modal(
      "Удалить задачу",
      "<p>Задача будет удалена из черновика плана.</p>",
      () => api("/api/tasks/" + id + "/", "DELETE"),
    );
  if (a === "submit") {
    const t = tasks.find((t) => t.id == id);
    return modal(
      "Результат: " + t.title,
      area("note", "Что сделано") +
        field(
          "evidence",
          t.photo_required ? "Обязательное фото" : "Фото при необходимости",
          "file",
          "",
          `accept=image/* ${t.photo_required ? "required" : ""}`,
        ),
      (fd) => {
        fd.set("task", id);
        if (!fd.get("evidence").size) fd.delete("evidence");
        return post("/api/completions/", fd);
      },
    );
  }
  if (a === "approve" || a === "reject")
    return modal(
      a === "approve" ? "Принять результат" : "Вернуть на доработку",
      area(
        "note",
        a === "approve" ? "Комментарий (необязательно)" : "Что нужно исправить",
      ),
      (fd) =>
        post("/api/completions/" + id + "/review/", {
          decision: a === "approve" ? "approved" : "rejected",
          note: fd.get("note"),
        }),
    );
  if (a === "incident")
    return modal(
      "Сообщить о проблеме",
      select("severity", "Важность", [
        ["normal", "Обычная"],
        ["urgent", "Срочная"],
      ]) + area("description", "Что произошло"),
      (fd) =>
        post("/api/incidents/", { handover: h.id, ...Object.fromEntries(fd) }),
    );
  if (a === "resolve")
    return modal(
      "Решение проблемы",
      area("resolution", "Что сделано для решения"),
      (fd) =>
        post("/api/incidents/" + id + "/resolve/", Object.fromEntries(fd)),
    );
  if (a === "photo") {
    const r = await fetch("/api/completions/" + id + "/evidence/", {
      headers: { Authorization: "Token " + token },
    });
    if (!r.ok) throw Error("Фото недоступно");
    const url = URL.createObjectURL(await r.blob());
    modal(
      "Фотоотчёт",
      `<img style="max-width:100%" alt="Фото результата" src="${url}">`,
      async () => {},
    );
    dialog.addEventListener("close", () => URL.revokeObjectURL(url), {
      once: true,
    });
  }
}
async function render() {
  if (!token) return auth();
  try {
    if (!me) me = await api("/api/users/me/");
    document.querySelector("#nav").hidden = false;
    let route = location.hash.slice(1) || "cats";
    if (route.startsWith("handover/")) await detail(route.split("/")[1]);
    else if (route === "handovers") await handovers();
    else await cats();
  } catch (err) {
    if (!token) return auth();
    app.innerHTML = `<section class="panel"><h1>Не удалось загрузить страницу</h1><p class="error">${e(err.message)}</p>${button("Повторить", "reload")}</section>`;
    app.querySelector("button").onclick = render;
  }
}
document.querySelector("#logout").onclick = async () => {
  try {
    await api("/api/token/logout/", "POST", {});
  } finally {
    token = null;
    me = null;
    sessionStorage.removeItem("kitty_token");
    render();
  }
};
window.addEventListener("hashchange", () => {
  page = 1;
  render();
});
render();
