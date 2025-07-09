let blockedCount = 0;
let hiddenCount = 0;

// Track blocked requests
chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
  blockedCount++;
  console.log(`Blocked: ${info.request.url} (Total: ${blockedCount})`);
  console.info(`[RULE STATS] Network rule triggered - Rule ID: ${info.rule.ruleId}, Priority: ${info.rule.priority}, Type: ${info.rule.action.type}, Domain: ${new URL(info.request.url).hostname}`);
});

// Reset count on navigation
chrome.webNavigation.onCommitted.addListener((details) => {
  if (details.frameId === 0) {
    blockedCount = 0;
    hiddenCount = 0;
  }
});

// Extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log('Shot-scraper extension started');
});

// Check when extension is installed/enabled
chrome.runtime.onInstalled.addListener(() => {
  console.log('Shot-scraper extension installed/enabled');
});

console.log('Shot-scraper background script loaded');

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
  
  return true;
});