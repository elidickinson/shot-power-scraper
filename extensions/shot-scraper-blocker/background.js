let blockedCount = 0;
let hiddenCount = 0;

// Track blocked requests
chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
  blockedCount++;
  console.log(`Blocked: ${info.request.url} (Total: ${blockedCount})`);
});

// Reset count on navigation
chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) {
    blockedCount = 0;
    hiddenCount = 0;
  }
});

// Handle popup requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "getBlockedCount") {
    sendResponse({ 
      blocked: blockedCount, 
      hidden: hiddenCount,
      total: blockedCount + hiddenCount
    });
  } else if (request.action === "updateHiddenCount") {
    hiddenCount = request.count;
  }
});