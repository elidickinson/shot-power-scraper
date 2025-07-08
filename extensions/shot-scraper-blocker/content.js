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
    
    // Check if selector is a valid element hiding selector (not CSS injection or other complex rules)
    function isValidElementHidingSelector(selector) {
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
    
    console.log(`Shot Scraper: Cosmetic filtering initialized`);
})();