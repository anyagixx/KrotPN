// FILE: apps/kpproton_portal/priv/static/request.js
// VERSION: 1.0.0
// START_MODULE_CONTRACT
//   PURPOSE: Drive the request page state machine for email submission, success, and error states.
//   SCOPE: Submit email to /api/request, show pending/success/error text, and disable the button during flight.
//   DEPENDS: apps/kpproton_portal/priv/static/index.html
//   LINKS: M-WEB-UI, M-WEB-API
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   setStatus - updates the visible request status card
//   maskEmail - redacts the local part of the email for safe UI telemetry
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added basic request flow state handling for the landing page.
// END_CHANGE_SUMMARY

const form = document.getElementById("request-form");
const emailInput = document.getElementById("email-input");
const submitButton = document.getElementById("submit-button");
const statusPanel = document.getElementById("request-status");
const statusTitle = document.getElementById("status-title");
const statusMessage = document.getElementById("status-message");

// START_BLOCK_STATUS_HELPERS
function setStatus(state, title, message) {
  statusPanel.dataset.state = state;
  statusTitle.textContent = title;
  statusMessage.textContent = message;
}

function maskEmail(email) {
  const [local, domain] = email.split("@");
  if (!domain || local.length < 2) {
    return "masked";
  }
  return `${local[0]}***@${domain}`;
}
// END_BLOCK_STATUS_HELPERS

// START_BLOCK_SUBMIT_HANDLER
form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = emailInput.value.trim();

  submitButton.disabled = true;
  console.info("[M-WEB-UI][submit][REQUEST_PROXY]", { email_masked: maskEmail(email) });
  setStatus("idle", "Отправляем письмо", "Проверяем запрос и готовим magic link.");

  try {
    const response = await fetch("/api/request", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(payload.error || "Не удалось отправить письмо. Попробуйте позже.");
    }

    console.info("[M-WEB-UI][state][SHOW_CHECK_EMAIL]", { email_masked: maskEmail(email) });
    setStatus("success", "Проверьте почту", "Мы отправили magic link. Откройте письмо и подтвердите адрес.");
    form.reset();
  } catch (error) {
    console.error("[M-WEB-UI][state][SHOW_ERROR]", { message: error.message });
    setStatus("error", "Запрос не отправлен", error.message);
  } finally {
    submitButton.disabled = false;
  }
});
// END_BLOCK_SUBMIT_HANDLER
