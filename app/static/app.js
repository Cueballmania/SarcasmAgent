"use strict";
const form = document.querySelector("#classify-form");
if (form) {
  const input = document.querySelector("#message");
  const button = document.querySelector("#submit");
  const result = document.querySelector("#result");
  const error = document.querySelector("#error");
  const requestId = document.querySelector("#request-id");
  const allowed = JSON.parse(form.dataset.labels);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (button.disabled) return;
    error.textContent = "";
    result.textContent = "";
    requestId.textContent = "";
    input.removeAttribute("aria-invalid");
    if (!input.value.trim() || Array.from(input.value).length > 2000) {
      error.textContent = "Enter 1 to 2,000 characters.";
      input.setAttribute("aria-invalid", "true");
      input.focus();
      return;
    }
    button.disabled = true;
    form.setAttribute("aria-busy", "true");
    result.textContent = "Detecting sarcasm...";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch("/api/classify", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input.value }),
        signal: controller.signal,
      });
      const data = await response.json();
      if (typeof data.request_id === "string") {
        requestId.textContent = `Request ID: ${data.request_id}`;
      }
      if (response.ok && allowed.includes(data.label)) {
        result.textContent = data.label;
      } else {
        result.textContent = "";
        error.textContent = data.error?.message || "The request failed; try later.";
      }
    } catch {
      result.textContent = "";
      error.textContent = "Network unavailable or request timed out. A retry counts as another request.";
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      form.removeAttribute("aria-busy");
    }
  });
}
