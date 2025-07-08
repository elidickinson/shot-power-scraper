// Get blocked count from background script
chrome.runtime.sendMessage({ action: "getBlockedCount" }, (response) => {
  if (response) {
    document.getElementById('blocked').textContent = response.blocked || 0;
    document.getElementById('hidden').textContent = response.hidden || 0;
    document.getElementById('total').textContent = response.total || 0;
  }
});