// Content script for ABP-compatible element hiding (cosmetic filtering)
(function() {
    'use strict';

    // Get extension name from manifest for distinguishing messages
    let extensionName = 'Unknown Extension';
    try {
        const manifest = chrome.runtime.getManifest();
        extensionName = manifest.name;
    } catch (e) {
        console.error('Failed to get extension name:', e);
    }

    let hiddenElements = 0;
    let cosmeticFilters = [];
    
    // Verbose mode enabled by default for debugging (can be disabled via localStorage)
    const verboseMode = localStorage.getItem('shot-scraper-verbose') !== 'false';

    // Execute JavaScript injection rules
    function executeScriptRule(scriptRule) {
        // Parse +js(function, arg1, arg2, ...) format
        const match = scriptRule.match(/^\+js\(([^)]+)\)$/);
        if (!match) return;

        const args = match[1].split(',').map(arg => arg.trim());
        const functionName = args[0];
        const functionArgs = args.slice(1);

        try {
            switch (functionName) {
                case 'rc':
                    // Remove class: rc(className, element, action)
                    if (functionArgs.length >= 1) {
                        const className = functionArgs[0];
                        const element = functionArgs[1] || 'html';
                        const action = functionArgs[2] || 'remove';

                        try {
                            const targetElement = element === 'html' ? document.documentElement :
                                                document.querySelector(element);

                            if (targetElement && className) {
                                if (action === 'remove' || action === 'stay') {
                                    targetElement.classList.remove(className);
                                }
                            }
                        } catch (e) {
                            if (verboseMode) {
                                console.warn(`[${extensionName}] rc scriptlet error:`, e, 'className:', className, 'element:', element);
                            }
                        }
                    }
                    break;

                case 'set':
                    // Set property: set(property, value)
                    if (functionArgs.length >= 2) {
                        let property = functionArgs[0];
                        const value = functionArgs[1];

                        try {
                            // Determine root object and clean property path
                            let rootObj = window;
                            if (property.startsWith('window.')) {
                                property = property.slice(7); // Remove 'window.' prefix
                            } else if (property.startsWith('document.')) {
                                rootObj = document;
                                property = property.slice(9); // Remove 'document.' prefix
                            }

                            // Navigate to target object
                            const keys = property.split('.');
                            let obj = rootObj;
                            for (let i = 0; i < keys.length - 1; i++) {
                                obj = obj[keys[i]] = obj[keys[i]] || {};
                            }
                            obj[keys[keys.length - 1]] = value;
                        } catch (e) {
                            if (verboseMode) {
                                console.warn(`[${extensionName}] set scriptlet error:`, e, 'property:', functionArgs[0], 'value:', functionArgs[1]);
                            }
                        }
                    }
                    break;

                case 'noeval':
                    // Disable eval
                    try {
                        window.eval = function() { return undefined; };
                        if (window.Function) {
                            window.Function.prototype.constructor = function() { return undefined; };
                        }
                    } catch (e) {
                        if (verboseMode) {
                            console.warn(`[${extensionName}] noeval scriptlet error:`, e);
                        }
                    }
                    break;

                default:
                    console.warn(`[${extensionName}] Unsupported script function:`, functionName);
                    break;
            }
        } catch (error) {
            console.warn(`[${extensionName}] Error executing script rule:`, scriptRule, error);
        }
    }


    // Check if rule applies to current domain
    function ruleApplies(rule, currentDomain) {
        if (!rule.domains) return true; // Universal rule

        return rule.domains.some(domain => {
            if (domain.startsWith('~')) {
                // Exception domain
                return !currentDomain.includes(domain.slice(1));
            } else {
                // Include domain
                return currentDomain.includes(domain);
            }
        });
    }

    // Apply element hiding rules
    function applyElementHiding() {
        const currentDomain = window.location.hostname;
        let newElementsHidden = 0;

        cosmeticFilters.forEach(rule => {
            if (!ruleApplies(rule, currentDomain)) return;

            try {
                if (rule.type === 'script') {
                    // Execute JavaScript injection rules
                    executeScriptRule(rule.selector);
                } else {
                    // Handle CSS selector rules
                    const elements = document.querySelectorAll(rule.selector);
                    elements.forEach(element => {
                        if (rule.type === 'hide') {
                            if (element.style.display !== 'none') {
                                element.style.display = 'none';
                                element.style.visibility = 'hidden';
                                element.setAttribute('data-shot-scraper-blocked', 'cosmetic');
                                hiddenElements++;
                                newElementsHidden++;
                            }
                        } else if (rule.type === 'unhide') {
                            // Remove hiding from unhide rules
                            element.style.display = '';
                            element.style.visibility = '';
                            element.removeAttribute('data-shot-scraper-blocked');
                            hiddenElements = Math.max(0, hiddenElements - 1);
                        }
                    });
                }
            } catch (error) {
                if (verboseMode || !rule.selector.includes('+js(')) {
                    // Always show CSS selector errors, only show JS errors in verbose mode
                    console.warn(`[${extensionName}] Invalid cosmetic filter selector:`, rule.selector, error);
                }
            }
        });

        if (newElementsHidden > 0) {
            console.info(`[${extensionName}] Cosmetic filtering - New elements hidden: ${newElementsHidden}, Total hidden: ${hiddenElements}`);
        }
    }

    // Load pre-processed cosmetic rules
    async function loadFilters() {
        try {
            const response = await fetch(chrome.runtime.getURL('cosmetic-rules.json'));
            cosmeticFilters = await response.json();
            console.log(`[${extensionName}] Loaded ${cosmeticFilters.length} pre-processed cosmetic filters`);

            // Apply filters once loaded
            applyElementHiding();
        } catch (error) {
            console.error(`[${extensionName}] Failed to load cosmetic filters:`, error);
        }
    }

    // Initialize
    loadFilters();

    // Apply filters as DOM changes
    const observer = new MutationObserver(() => {
        if (cosmeticFilters.length > 0) {
            applyElementHiding();
        }
    });

    // Start observing when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, { childList: true, subtree: true });
        });
    } else {
        observer.observe(document.body, { childList: true, subtree: true });
    }

    // Report blocked elements count to background script
    setInterval(() => {
        chrome.runtime.sendMessage({
            action: 'updateHiddenCount',
            count: hiddenElements
        });
    }, 1000);

    console.log(`[${extensionName}] Cosmetic filtering initialized`);
})();
