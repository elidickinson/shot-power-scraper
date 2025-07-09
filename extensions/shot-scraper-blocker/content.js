// Content script for ABP-compatible element hiding (cosmetic filtering)
(function() {
    'use strict';
    
    let hiddenElements = 0;
    let cosmeticFilters = [];
    
    // Parse ABP element hiding rules
    function parseElementHidingRules(filterText) {
        const lines = filterText.split('\n');
        const rules = [];
        
        for (const line of lines) {
            const trimmed = line.trim();
            
            // Skip comments and empty lines
            if (!trimmed || trimmed.startsWith('!')) continue;
            
            // Parse element hiding rules (##selector)
            if (trimmed.includes('##')) {
                const parts = trimmed.split('##');
                if (parts.length === 2) {
                    const domains = parts[0] || null;
                    const selector = parts[1];
                    
                    if (selector && isValidElementHidingSelector(selector)) {
                        rules.push({
                            domains: domains ? domains.split(',') : null,
                            selector: selector,
                            type: 'hide'
                        });
                    }
                }
            }
            
            // Parse element unhiding rules (#@#selector)
            if (trimmed.includes('#@#')) {
                const parts = trimmed.split('#@#');
                if (parts.length === 2) {
                    const domains = parts[0] || null;
                    const selector = parts[1];
                    
                    if (selector && isValidElementHidingSelector(selector)) {
                        rules.push({
                            domains: domains ? domains.split(',') : null,
                            selector: selector,
                            type: 'unhide'
                        });
                    }
                }
            }
        }
        
        return rules;
    }
    
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
                        
                        const targetElement = element === 'html' ? document.documentElement : 
                                            document.querySelector(element);
                        
                        if (targetElement) {
                            if (action === 'remove' || action === 'stay') {
                                targetElement.classList.remove(className);
                            }
                        }
                    }
                    break;
                
                case 'set':
                    // Set property: set(property, value)
                    if (functionArgs.length >= 2) {
                        const property = functionArgs[0];
                        const value = functionArgs[1];
                        
                        try {
                            const keys = property.split('.');
                            let obj = window;
                            for (let i = 0; i < keys.length - 1; i++) {
                                obj = obj[keys[i]] = obj[keys[i]] || {};
                            }
                            obj[keys[keys.length - 1]] = value;
                        } catch (e) {
                            // Ignore errors in property setting
                        }
                    }
                    break;
                
                case 'noeval':
                    // Disable eval
                    try {
                        window.eval = function() { return false; };
                    } catch (e) {
                        // Ignore errors
                    }
                    break;
                
                default:
                    console.warn('Unsupported script function:', functionName);
                    break;
            }
        } catch (error) {
            console.warn('Error executing script rule:', scriptRule, error);
        }
    }
    
    // Check if selector is a valid element hiding selector (not CSS injection or other complex rules)
    function isValidElementHidingSelector(selector) {
        // Support JavaScript injection rules (+js)
        if (selector.startsWith('+js(') && selector.endsWith(')')) {
            return true;
        }
        
        // Skip CSS injection rules (:style(), :remove(), etc.)
        if (selector.includes(':style(') || 
            selector.includes(':remove(') || 
            selector.includes(':has-text(') ||
            selector.includes(':matches-css(') ||
            selector.includes(':xpath(') ||
            selector.includes('>>>') ||
            selector.includes('^')) {
            return false;
        }
        
        // Test if it's a valid CSS selector
        try {
            document.createDocumentFragment().querySelector(selector);
            return true;
        } catch (e) {
            return false;
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
                console.warn('Invalid cosmetic filter selector:', rule.selector, error);
            }
        });
    }
    
    // Load pre-processed cosmetic rules
    async function loadFilters() {
        try {
            const response = await fetch(chrome.runtime.getURL('cosmetic_rules.json'));
            cosmeticFilters = await response.json();
            console.log(`Loaded ${cosmeticFilters.length} pre-processed cosmetic filters`);
            
            // Apply filters once loaded
            applyElementHiding();
        } catch (error) {
            console.error('Failed to load cosmetic filters:', error);
        }
    }
    
    // Initialize
    loadFilters();
    
    // Continue applying filters as DOM changes
    const observer = new MutationObserver(() => {
        if (cosmeticFilters.length > 0) {
            applyElementHiding();
        }
    });
    
    // Start observing when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        });
    } else {
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Periodic check for new elements
    setInterval(() => {
        if (cosmeticFilters.length > 0) {
            applyElementHiding();
        }
    }, 2000);
    
    // Report blocked elements count to background script
    setInterval(() => {
        chrome.runtime.sendMessage({
            action: 'updateHiddenCount',
            count: hiddenElements
        });
    }, 1000);
    
    console.log('Shot Scraper: Cosmetic filtering initialized');
})();