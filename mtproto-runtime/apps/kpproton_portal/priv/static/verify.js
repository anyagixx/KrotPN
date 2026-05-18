// FILE: apps/kpproton_portal/priv/static/verify.js
// VERSION: 1.0.0
// START_MODULE_CONTRACT
//   PURPOSE: Add copy-to-clipboard behavior and small feedback interactions to the verify result page.
//   SCOPE: Copy tg://proxy, server, port, and secret values from the success result view.
//   DEPENDS: verify-result markup rendered by kpproton_verify_handler.erl
//   LINKS: M-VERIFY-UX
// END_MODULE_CONTRACT
//
// START_MODULE_MAP
//   updateCopyState - shows temporary copied feedback for a pressed button
// END_MODULE_MAP
//
// START_CHANGE_SUMMARY
//   LAST_CHANGE: v1.0.0 - Added copy-to-clipboard support for verify result fields.
// END_CHANGE_SUMMARY

function updateCopyState(button, label) {
  const previous = button.textContent;
  button.textContent = label;
  button.disabled = true;
  window.setTimeout(() => {
    button.textContent = previous;
    button.disabled = false;
  }, 1400);
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const target = document.getElementById(button.dataset.copy);
    if (!target) return;
    const value = target.dataset.copyValue || target.textContent || "";
    try {
      await navigator.clipboard.writeText(value.trim());
      updateCopyState(button, "Скопировано");
    } catch (_error) {
      updateCopyState(button, "Скопируйте вручную");
    }
  });
});
