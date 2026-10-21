(() => {
  "use strict";

  const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";
  const notice = document.getElementById("notice");

  function showNotice(message, type = "success") {
    if (!notice) return;
    notice.textContent = message;
    notice.className = `notice notice-${type}`;
    notice.hidden = false;
    window.clearTimeout(showNotice.timer);
    showNotice.timer = window.setTimeout(() => {
      notice.hidden = true;
    }, 5500);
  }

  async function apiRequest(endpoint, method, payload) {
    const options = {
      method,
      credentials: "same-origin",
      headers: { Accept: "application/json", "X-CSRF-Token": csrfToken() },
    };
    if (payload !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(payload);
    }
    const response = await fetch(endpoint, options);
    let body;
    try {
      body = await response.json();
    } catch (_error) {
      body = { success: false, error: { message: "The server returned an unreadable response." } };
    }
    if (!response.ok) {
      const problem = new Error(body.error?.message || `Request failed (${response.status}).`);
      problem.status = response.status;
      problem.code = body.error?.code;
      throw problem;
    }
    return body;
  }

  document.querySelectorAll("[data-api-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (form.dataset.busy === "true") return;
      const submit = form.querySelector('[type="submit"]');
      const oldText = submit?.textContent;
      const payload = Object.fromEntries(new FormData(form).entries());
      form.dataset.busy = "true";
      if (submit) {
        submit.disabled = true;
        submit.textContent = "Working…";
      }
      try {
        const result = await apiRequest(form.dataset.endpoint || form.action, form.dataset.method || "POST", payload);
        showNotice(result.message || "Done.");
        const template = form.dataset.redirectTemplate;
        if (template) {
          window.setTimeout(() => window.location.assign(template.replace("{id}", result.data.id)), 350);
        } else if (form.dataset.redirect) {
          window.setTimeout(() => window.location.assign(form.dataset.redirect), 350);
        } else if (form.dataset.reload === "true") {
          window.setTimeout(() => window.location.reload(), 350);
        } else {
          form.reset();
        }
      } catch (problem) {
        showNotice(problem.message, "error");
        const firstField = form.querySelector("input:invalid, select:invalid, textarea:invalid");
        firstField?.focus();
      } finally {
        form.dataset.busy = "false";
        if (submit) {
          submit.disabled = false;
          submit.textContent = oldText;
        }
      }
    });
  });

  document.querySelectorAll("[data-feedback-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const form = document.getElementById(button.dataset.feedbackToggle);
      if (!form) return;
      form.hidden = !form.hidden;
      button.setAttribute("aria-expanded", String(!form.hidden));
      if (!form.hidden) form.querySelector("select")?.focus();
    });
  });

  document.querySelectorAll("[data-character-count]").forEach((counter) => {
    const field = document.getElementById(counter.dataset.characterCount);
    field?.addEventListener("input", () => {
      counter.textContent = String(field.value.length);
    });
  });

  const navToggle = document.querySelector(".nav-toggle");
  const navigation = document.getElementById("main-nav");
  navToggle?.addEventListener("click", () => {
    const open = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!open));
    navigation?.classList.toggle("is-open", !open);
  });

  window.Padeli = { apiRequest, showNotice };
})();

