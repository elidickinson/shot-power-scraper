console.log('Test extension loaded successfully!');

chrome.runtime.onInstalled.addListener(() => {
  console.log('Test extension installed');
});

chrome.runtime.onStartup.addListener(() => {
  console.log('Test extension started');
});