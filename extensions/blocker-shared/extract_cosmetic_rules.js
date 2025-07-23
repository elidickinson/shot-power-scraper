#!/usr/bin/env node

// Extract and filter cosmetic rules from ABP filter lists
const fs = require('fs');
const path = require('path');

// Check if selector is a valid element hiding selector
function isValidElementHidingSelector(selector) {
    // Support JavaScript injection rules (+js)
    if (selector.startsWith('+js(') && selector.endsWith(')')) {
        return true;
    }
    
    // Skip CSS injection rules and other complex ABP extensions (but not +js)
    if (selector.includes(':style(') || 
        selector.includes(':remove(') || 
        selector.includes(':has-text(') ||
        selector.includes(':matches-css(') ||
        selector.includes(':xpath(') ||
        selector.includes('>>>') ||
        selector.includes('^')) {
        return false;
    }
    
    // Skip overly complex selectors that might cause performance issues
    if (selector.length > 200) {
        return false;
    }
    
    // Basic CSS selector validation (simple heuristic)
    const invalidChars = /[<>{}]/;
    if (invalidChars.test(selector)) {
        return false;
    }
    
    return true;
}

// Parse ABP element hiding rules from filter text
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
                    const ruleType = selector.startsWith('+js(') ? 'script' : 'hide';
                    rules.push({
                        domains: domains ? domains.split(',') : null,
                        selector: selector,
                        type: ruleType
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

// Analyze filter file and return statistics
function analyzeFilterFile(inputFile) {
    if (!fs.existsSync(inputFile)) {
        return null;
    }
    
    const filterText = fs.readFileSync(inputFile, 'utf8');
    const lines = filterText.split('\n');
    
    let stats = {
        totalLines: lines.length,
        comments: 0,
        networkRules: 0,
        cosmeticRules: 0,
        scriptRules: 0,
        unsupportedRules: 0,
        validCosmeticRules: 0
    };
    
    for (const line of lines) {
        const trimmed = line.trim();
        
        if (!trimmed) continue;
        
        if (trimmed.startsWith('!')) {
            stats.comments++;
        } else if (trimmed.includes('##') || trimmed.includes('#@#')) {
            stats.cosmeticRules++;
            
            // Check if it's a valid cosmetic rule
            const parts = trimmed.includes('##') ? trimmed.split('##') : trimmed.split('#@#');
            if (parts.length === 2) {
                const selector = parts[1];
                if (selector && isValidElementHidingSelector(selector)) {
                    if (selector.startsWith('+js(')) {
                        stats.scriptRules++;
                    } else {
                        stats.validCosmeticRules++;
                    }
                } else {
                    stats.unsupportedRules++;
                }
            }
        } else {
            // Assume it's a network rule
            stats.networkRules++;
        }
    }
    
    return stats;
}

// Process filter file
function processFilterFile(inputFile, outputFile) {
    if (!fs.existsSync(inputFile)) {
        console.error(`Filter file not found: ${inputFile}`);
        return false;
    }
    
    const filterText = fs.readFileSync(inputFile, 'utf8');
    const rules = parseElementHidingRules(filterText);
    
    console.log(`Extracted ${rules.length} valid cosmetic rules from ${inputFile}`);
    
    // Write as JSON for easy loading in content script
    fs.writeFileSync(outputFile, JSON.stringify(rules, null, 2));
    
    return true;
}

// Main function
function main() {
    const args = process.argv.slice(2);
    
    if (args.length < 1) {
        console.error('Usage: node extract_cosmetic_rules.js [--stats] <input.txt> [output.json]');
        process.exit(1);
    }
    
    // Check for --stats flag
    if (args[0] === '--stats') {
        if (args.length < 2) {
            console.error('Usage: node extract_cosmetic_rules.js --stats <input.txt>');
            process.exit(1);
        }
        
        const inputFile = args[1];
        const stats = analyzeFilterFile(inputFile);
        
        if (stats) {
            console.log(JSON.stringify(stats, null, 2));
        } else {
            console.error(`Filter file not found: ${inputFile}`);
            process.exit(1);
        }
        return;
    }
    
    if (args.length < 2) {
        console.error('Usage: node extract_cosmetic_rules.js <input.txt> <output.json>');
        process.exit(1);
    }
    
    const inputFile = args[0];
    const outputFile = args[1];
    
    if (processFilterFile(inputFile, outputFile)) {
        console.log(`Cosmetic rules saved to ${outputFile}`);
    } else {
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { parseElementHidingRules, isValidElementHidingSelector, analyzeFilterFile };