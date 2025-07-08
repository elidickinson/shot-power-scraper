// Get blocked count from background script
chrome.runtime.sendMessage({ action: "getBlockedCount" }, (response) => {
  if (response && response.count !== undefined) {
    document.getElementById('blocked').textContent = response.count;
  }
});