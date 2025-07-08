console.log('Simple Ad Blocker loaded');

// Listen for blocked requests (for debugging)
chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
  console.log('Blocked:', info.request.url, 'by rule:', info.rule.ruleId);
});