let blockedCount = 0;

// Track blocked requests
chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
  blockedCount++;
  console.log(`Blocked: ${info.request.url} (Total: ${blockedCount})`);
});

// Reset count on navigation
chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) {
    blockedCount = 0;
  }
});

// Handle popup requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getBlockedCount") {
    sendResponse({ count: blockedCount });
  }
});