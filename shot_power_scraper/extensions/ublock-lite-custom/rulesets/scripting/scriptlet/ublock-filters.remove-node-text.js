/*******************************************************************************

    uBlock Origin Lite - a comprehensive, MV3-compliant content blocker
    Copyright (C) 2014-present Raymond Hill

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see {http://www.gnu.org/licenses/}.

    Home: https://github.com/gorhill/uBlock

*/

// ruleset: ublock-filters

// Important!
// Isolate from global scope

// Start of local scope
(function uBOL_removeNodeText() {

/******************************************************************************/

function removeNodeText(
    nodeName,
    includes,
    ...extraArgs
) {
    replaceNodeTextFn(nodeName, '', '', 'includes', includes || '', ...extraArgs);
}

function replaceNodeTextFn(
    nodeName = '',
    pattern = '',
    replacement = ''
) {
    const safe = safeSelf();
    const logPrefix = safe.makeLogPrefix('replace-node-text.fn', ...Array.from(arguments));
    const reNodeName = safe.patternToRegex(nodeName, 'i', true);
    const rePattern = safe.patternToRegex(pattern, 'gms');
    const extraArgs = safe.getExtraArgs(Array.from(arguments), 3);
    const reIncludes = extraArgs.includes || extraArgs.condition
        ? safe.patternToRegex(extraArgs.includes || extraArgs.condition, 'ms')
        : null;
    const reExcludes = extraArgs.excludes
        ? safe.patternToRegex(extraArgs.excludes, 'ms')
        : null;
    const stop = (takeRecord = true) => {
        if ( takeRecord ) {
            handleMutations(observer.takeRecords());
        }
        observer.disconnect();
        if ( safe.logLevel > 1 ) {
            safe.uboLog(logPrefix, 'Quitting');
        }
    };
    const textContentFactory = (( ) => {
        const out = { createScript: s => s };
        const { trustedTypes: tt } = self;
        if ( tt instanceof Object ) {
            if ( typeof tt.getPropertyType === 'function' ) {
                if ( tt.getPropertyType('script', 'textContent') === 'TrustedScript' ) {
                    return tt.createPolicy(getRandomTokenFn(), out);
                }
            }
        }
        return out;
    })();
    let sedCount = extraArgs.sedCount || 0;
    const handleNode = node => {
        const before = node.textContent;
        if ( reIncludes ) {
            reIncludes.lastIndex = 0;
            if ( safe.RegExp_test.call(reIncludes, before) === false ) { return true; }
        }
        if ( reExcludes ) {
            reExcludes.lastIndex = 0;
            if ( safe.RegExp_test.call(reExcludes, before) ) { return true; }
        }
        rePattern.lastIndex = 0;
        if ( safe.RegExp_test.call(rePattern, before) === false ) { return true; }
        rePattern.lastIndex = 0;
        const after = pattern !== ''
            ? before.replace(rePattern, replacement)
            : replacement;
        node.textContent = node.nodeName === 'SCRIPT'
            ? textContentFactory.createScript(after)
            : after;
        if ( safe.logLevel > 1 ) {
            safe.uboLog(logPrefix, `Text before:\n${before.trim()}`);
        }
        safe.uboLog(logPrefix, `Text after:\n${after.trim()}`);
        return sedCount === 0 || (sedCount -= 1) !== 0;
    };
    const handleMutations = mutations => {
        for ( const mutation of mutations ) {
            for ( const node of mutation.addedNodes ) {
                if ( reNodeName.test(node.nodeName) === false ) { continue; }
                if ( handleNode(node) ) { continue; }
                stop(false); return;
            }
        }
    };
    const observer = new MutationObserver(handleMutations);
    observer.observe(document, { childList: true, subtree: true });
    if ( document.documentElement ) {
        const treeWalker = document.createTreeWalker(
            document.documentElement,
            NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT
        );
        let count = 0;
        for (;;) {
            const node = treeWalker.nextNode();
            count += 1;
            if ( node === null ) { break; }
            if ( reNodeName.test(node.nodeName) === false ) { continue; }
            if ( node === document.currentScript ) { continue; }
            if ( handleNode(node) ) { continue; }
            stop(); break;
        }
        safe.uboLog(logPrefix, `${count} nodes present before installing mutation observer`);
    }
    if ( extraArgs.stay ) { return; }
    runAt(( ) => {
        const quitAfter = extraArgs.quitAfter || 0;
        if ( quitAfter !== 0 ) {
            setTimeout(( ) => { stop(); }, quitAfter);
        } else {
            stop();
        }
    }, 'interactive');
}

function getRandomTokenFn() {
    const safe = safeSelf();
    return safe.String_fromCharCode(Date.now() % 26 + 97) +
        safe.Math_floor(safe.Math_random() * 982451653 + 982451653).toString(36);
}

function runAt(fn, when) {
    const intFromReadyState = state => {
        const targets = {
            'loading': 1, 'asap': 1,
            'interactive': 2, 'end': 2, '2': 2,
            'complete': 3, 'idle': 3, '3': 3,
        };
        const tokens = Array.isArray(state) ? state : [ state ];
        for ( const token of tokens ) {
            const prop = `${token}`;
            if ( Object.hasOwn(targets, prop) === false ) { continue; }
            return targets[prop];
        }
        return 0;
    };
    const runAt = intFromReadyState(when);
    if ( intFromReadyState(document.readyState) >= runAt ) {
        fn(); return;
    }
    const onStateChange = ( ) => {
        if ( intFromReadyState(document.readyState) < runAt ) { return; }
        fn();
        safe.removeEventListener.apply(document, args);
    };
    const safe = safeSelf();
    const args = [ 'readystatechange', onStateChange, { capture: true } ];
    safe.addEventListener.apply(document, args);
}

function safeSelf() {
    if ( scriptletGlobals.safeSelf ) {
        return scriptletGlobals.safeSelf;
    }
    const self = globalThis;
    const safe = {
        'Array_from': Array.from,
        'Error': self.Error,
        'Function_toStringFn': self.Function.prototype.toString,
        'Function_toString': thisArg => safe.Function_toStringFn.call(thisArg),
        'Math_floor': Math.floor,
        'Math_max': Math.max,
        'Math_min': Math.min,
        'Math_random': Math.random,
        'Object': Object,
        'Object_defineProperty': Object.defineProperty.bind(Object),
        'Object_defineProperties': Object.defineProperties.bind(Object),
        'Object_fromEntries': Object.fromEntries.bind(Object),
        'Object_getOwnPropertyDescriptor': Object.getOwnPropertyDescriptor.bind(Object),
        'Object_hasOwn': Object.hasOwn.bind(Object),
        'RegExp': self.RegExp,
        'RegExp_test': self.RegExp.prototype.test,
        'RegExp_exec': self.RegExp.prototype.exec,
        'Request_clone': self.Request.prototype.clone,
        'String': self.String,
        'String_fromCharCode': String.fromCharCode,
        'String_split': String.prototype.split,
        'XMLHttpRequest': self.XMLHttpRequest,
        'addEventListener': self.EventTarget.prototype.addEventListener,
        'removeEventListener': self.EventTarget.prototype.removeEventListener,
        'fetch': self.fetch,
        'JSON': self.JSON,
        'JSON_parseFn': self.JSON.parse,
        'JSON_stringifyFn': self.JSON.stringify,
        'JSON_parse': (...args) => safe.JSON_parseFn.call(safe.JSON, ...args),
        'JSON_stringify': (...args) => safe.JSON_stringifyFn.call(safe.JSON, ...args),
        'log': console.log.bind(console),
        // Properties
        logLevel: 0,
        // Methods
        makeLogPrefix(...args) {
            return this.sendToLogger && `[${args.join(' \u205D ')}]` || '';
        },
        uboLog(...args) {
            if ( this.sendToLogger === undefined ) { return; }
            if ( args === undefined || args[0] === '' ) { return; }
            return this.sendToLogger('info', ...args);
            
        },
        uboErr(...args) {
            if ( this.sendToLogger === undefined ) { return; }
            if ( args === undefined || args[0] === '' ) { return; }
            return this.sendToLogger('error', ...args);
        },
        escapeRegexChars(s) {
            return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        },
        initPattern(pattern, options = {}) {
            if ( pattern === '' ) {
                return { matchAll: true, expect: true };
            }
            const expect = (options.canNegate !== true || pattern.startsWith('!') === false);
            if ( expect === false ) {
                pattern = pattern.slice(1);
            }
            const match = /^\/(.+)\/([gimsu]*)$/.exec(pattern);
            if ( match !== null ) {
                return {
                    re: new this.RegExp(
                        match[1],
                        match[2] || options.flags
                    ),
                    expect,
                };
            }
            if ( options.flags !== undefined ) {
                return {
                    re: new this.RegExp(this.escapeRegexChars(pattern),
                        options.flags
                    ),
                    expect,
                };
            }
            return { pattern, expect };
        },
        testPattern(details, haystack) {
            if ( details.matchAll ) { return true; }
            if ( details.re ) {
                return this.RegExp_test.call(details.re, haystack) === details.expect;
            }
            return haystack.includes(details.pattern) === details.expect;
        },
        patternToRegex(pattern, flags = undefined, verbatim = false) {
            if ( pattern === '' ) { return /^/; }
            const match = /^\/(.+)\/([gimsu]*)$/.exec(pattern);
            if ( match === null ) {
                const reStr = this.escapeRegexChars(pattern);
                return new RegExp(verbatim ? `^${reStr}$` : reStr, flags);
            }
            try {
                return new RegExp(match[1], match[2] || undefined);
            }
            catch {
            }
            return /^/;
        },
        getExtraArgs(args, offset = 0) {
            const entries = args.slice(offset).reduce((out, v, i, a) => {
                if ( (i & 1) === 0 ) {
                    const rawValue = a[i+1];
                    const value = /^\d+$/.test(rawValue)
                        ? parseInt(rawValue, 10)
                        : rawValue;
                    out.push([ a[i], value ]);
                }
                return out;
            }, []);
            return this.Object_fromEntries(entries);
        },
        onIdle(fn, options) {
            if ( self.requestIdleCallback ) {
                return self.requestIdleCallback(fn, options);
            }
            return self.requestAnimationFrame(fn);
        },
        offIdle(id) {
            if ( self.requestIdleCallback ) {
                return self.cancelIdleCallback(id);
            }
            return self.cancelAnimationFrame(id);
        }
    };
    scriptletGlobals.safeSelf = safe;
    if ( scriptletGlobals.bcSecret === undefined ) { return safe; }
    // This is executed only when the logger is opened
    safe.logLevel = scriptletGlobals.logLevel || 1;
    let lastLogType = '';
    let lastLogText = '';
    let lastLogTime = 0;
    safe.toLogText = (type, ...args) => {
        if ( args.length === 0 ) { return; }
        const text = `[${document.location.hostname || document.location.href}]${args.join(' ')}`;
        if ( text === lastLogText && type === lastLogType ) {
            if ( (Date.now() - lastLogTime) < 5000 ) { return; }
        }
        lastLogType = type;
        lastLogText = text;
        lastLogTime = Date.now();
        return text;
    };
    try {
        const bc = new self.BroadcastChannel(scriptletGlobals.bcSecret);
        let bcBuffer = [];
        safe.sendToLogger = (type, ...args) => {
            const text = safe.toLogText(type, ...args);
            if ( text === undefined ) { return; }
            if ( bcBuffer === undefined ) {
                return bc.postMessage({ what: 'messageToLogger', type, text });
            }
            bcBuffer.push({ type, text });
        };
        bc.onmessage = ev => {
            const msg = ev.data;
            switch ( msg ) {
            case 'iamready!':
                if ( bcBuffer === undefined ) { break; }
                bcBuffer.forEach(({ type, text }) =>
                    bc.postMessage({ what: 'messageToLogger', type, text })
                );
                bcBuffer = undefined;
                break;
            case 'setScriptletLogLevelToOne':
                safe.logLevel = 1;
                break;
            case 'setScriptletLogLevelToTwo':
                safe.logLevel = 2;
                break;
            }
        };
        bc.postMessage('areyouready?');
    } catch {
        safe.sendToLogger = (type, ...args) => {
            const text = safe.toLogText(type, ...args);
            if ( text === undefined ) { return; }
            safe.log(`uBO ${text}`);
        };
    }
    return safe;
}

/******************************************************************************/

const scriptletGlobals = {}; // eslint-disable-line
const argsList = [["script","window,\"fetch\""],["script","offsetParent"],["script","/adblock/i"],["script","location.reload"],["script","/google_jobrunner|AdBlock|pubadx|embed\\.html/i"],["script","/aps_csm|snigelweb|gettheName|YWRuZ2lu|adngin|sighsigh|mycool|100vh|apple-system/"],["script","adserverDomain","excludes","debugger"],["script","adBlockEnabled"],["script","\"Anzeige\""],["script","adserverDomain"],["script","Promise"],["script","/adbl/i"],["script","Reflect"],["script","document.write"],["script","self == top"],["script","exdynsrv"],["script","/delete window|adserverDomain|FingerprintJS/"],["script","delete window"],["script","adsbygoogle"],["script","FingerprintJS"],["script","/adblock.php"],["script","/adb/i"],["script","/document\\.createElement|\\.banner-in/"],["script","admbenefits"],["script","/\\badblock\\b/"],["script","myreadCookie"],["script","ExoLoader"],["script","/?key.*open/","condition","key"],["script","adblock"],["script","homad"],["script","popUnderUrl"],["script","Adblock"],["script","WebAssembly"],["script","detectAdBlock"],["script","/ABDetected|navigator.brave|fetch/"],["script","/ai_|b2a/"],["script","deblocker"],["script","/DName|#iframe_id/"],["script","adblockDetector"],["script","/bypass.php"],["script","htmls"],["script","toast"],["script","AdbModel"],["script","/popup/i"],["script","antiAdBlockerHandler"],["script","/ad\\s?block|adsBlocked|document\\.write\\(unescape\\('|devtool/i"],["script","onerror"],["script","/checkAdBlocker|AdblockRegixFinder/"],["script","catch"],["script","/adb_detected|AdBlockCheck|;break;case \\$\\./i"],["script","window.open"],["script","/aclib|break;|zoneNativeSett/"],["script","/fetch|popupshow/"],["script","justDetectAdblock"],["script","/FingerprintJS|openPopup/"],["script","DisableDevtool"],["script","popUp"],["script","/adsbygoogle|detectAdBlock/"],["script","onDevToolOpen"],["script","firstp"],["script","ctrlKey"],["script","/\\);break;case|advert_|POPUNDER_URL|adblock/"],["script","DisplayAcceptableAdIfAdblocked"],["script","adslotFilledByCriteo"],["script","/==undefined.*body/"],["script","/popunder|isAdBlock|admvn.src/i"],["script","/h=decodeURIComponent|popundersPerIP/"],["script","/h=decodeURIComponent|\"popundersPerIP\"/"],["script","popMagic"],["script","/popMagic|pop1stp/"],["script","/exoloader/i"],["script","/shown_at|WebAssembly/"],["script",";}}};break;case $."],["script","globalThis;break;case"],["script","{delete window["],["script","wpadmngr.com"],["script","\"adserverDomain\""],["script","sandbox"],["script","/decodeURIComponent\\(escape|fairAdblock/"],["script","/ai_|googletag|adb/"],["script","adsBlocked"],["script","ai_adb"],["script","\"v4ac1eiZr0\""],["script","admiral"],["script","'').split(',')[4]"],["script","/\"v4ac1eiZr0\"|\"\"\\)\\.split\\(\",\"\\)\\[4\\]|(\\.localStorage\\)|JSON\\.parse\\(\\w)\\.getItem\\(\"|[\"']_aQS0\\w+[\"']/"],["script","error-report.com"],["script","html-load.com"],["script","KCgpPT57bGV0IGU"],["script","Ad-Shield"],["script","adrecover.com"],["script","\"data-sdk\""],["script","/wcomAdBlock|error-report\\.com/"],["script","head.appendChild.bind"],["script","/^\\(async\\(\\)=>\\{function.{1,200}head.{1,100}\\.bind.{1,900}location\\.href.{1,100}\\}\\)\\(\\);$/"],["script","/adblock|popunder|openedPop|WebAssembly|wpadmngr/"],["script","/detectAdblock|WebAssembly|pop1stp|popMagic/i"],["script","_ADX_"],["script","div.offsetHeight"],["script","/adbl|RegExp/i"],["script","/WebAssembly|forceunder/"],["script","/isAdBlocked|popUnderUrl/"],["script","/adb|offsetWidth|eval/i"],["script","contextmenu"],["script","/adblock|var Data.*];/"],["script","var Data"],["script","replace"],["style","text-decoration"],["script","/break;case|FingerprintJS/"],["script","push"],["script","AdBlocker"],["script","clicky"],["script","XV"],["script","Popunder"],["script","charCodeAt"],["script","localStorage"],["script","popunder"],["script","adbl"],["script","googlesyndication"],["script","blockAdBlock"],["script","/downloadJSAtOnload|Object.prototype.toString.call/"],["script","numberPages"],["script","brave"],["script","AreLoaded"],["script","AdblockRegixFinder"],["script","/adScript|adsBlocked/"],["script","serve"],["script","?metric=transit.counter&key=fail_redirect&tags="],["script","/pushAdTag|link_click|getAds/"],["script","/\\', [0-9]{5}\\)\\]\\; \\}/"],["script","/\\\",\\\"clickp\\\"\\:\\\"[0-9]{1,2}\\\"/"],["script","/ConsoleBan|alert|AdBlocker/"],["style","body:not(.ownlist)"],["script","mdpDeblocker"],["script","alert","condition","adblock"],["script","/deblocker|chp_ad/"],["script","await fetch"],["script","AdBlock"],["script","/'.adsbygoogle'|text-danger|warning|Adblock|_0x/"],["script","insertAdjacentHTML"],["script","popUnder"],["script","adb"],["#text","/スポンサーリンク|Sponsored Link|广告/"],["#text","スポンサーリンク"],["#text","スポンサードリンク"],["#text","/\\[vkExUnit_ad area=(after|before)\\]/"],["#text","【広告】"],["#text","関連動画"],["#text","PR:"],["script","leave_recommend"],["#text","/Advertisement/"],["script","navigator.brave"],["script","liedetector"],["script","end_click"],["script","getComputedStyle"],["script","closeAd"],["script","/adconfig/i"],["script","is_antiblock_refresh"],["script","/userAgent|adb|htmls/"],["script","myModal"],["script","open"],["script","app_checkext"],["script","ad blocker"],["script","clientHeight"],["script","Brave"],["script","await"],["script","axios"],["script","/charAt|XMLHttpRequest/"],["script","AdBlockEnabled"],["script","window.location.replace"],["script","egoTab"],["script","/$.*(css|oncontextmenu)/"],["script","/eval.*RegExp/"],["script","wwads"],["script","popundersPerIP"],["script","/ads?Block/i"],["script","chkADB"],["script","Symbol.iterator"],["script","ai_cookie"],["script","/innerHTML.*appendChild/"],["script","Exo"],["script","AaDetector"],["script","/window\\[\\'open\\'\\]/"],["script","Error"],["script","/document\\.head\\.appendChild|window\\.open/"],["script","pop1stp"],["script","Number"],["script","NEXT_REDIRECT"],["script","ad-block-activated"],["script","pop.doEvent"],["script","Ads"],["script","detect"],["script","fetch"],["script","/hasAdblock|detect/"],["script","document.createTextNode"],["script","adsSrc"],["script","/popMagic|nativeads|navigator\\.brave|\\.abk_msg|\\.innerHTML|ad block|manipulation/"],["script","window.warn"],["script","adBlock"],["script","adBlockDetected"],["script","/fetch|adb/i"],["script","location"],["script","showAd"],["script","imgSrc"],["script","document.createElement(\"script\")"],["script","antiAdBlock"],["script","/fairAdblock|popMagic/"],["script","aclib.runPop"],["script","mega-enlace.com/ext.php?o="],["script","Popup"],["script","displayAdsV3"],["script","adblocker"],["script","break;case"],["h2","/creeperhost/i"],["script","/interceptClickEvent|onbeforeunload|popMagic|location\\.replace/"],["script","/adserverDomain|\\);break;case /"],["script","initializeInterstitial"],["script","popupBackground"],["script","/h=decodeURIComponent|popundersPerIP|adserverDomain/"],["script","m9-ad-modal"],["script","Anzeige"],["script","blocking"],["script","HTMLAllCollection"],["script","LieDetector"],["script","advads"],["script","document.cookie"],["script","/h=decodeURIComponent|popundersPerIP|window\\.open|\\.createElement/"],["script","/_0x|brave|onerror/"],["script","window.googletag.pubads"],["script","'hidden'"],["script","kmtAdsData"],["script","navigator.userAgent"],["script","checkAdBlock"],["script","detectedAdblock"],["script","setADBFlag"],["script","/h=decodeURIComponent|popundersPerIP|wpadmngr|popMagic/"],["script","/wpadmngr|adserverDomain/"],["script","/account_ad_blocker|tmaAB/"],["script","ads_block"],["script","/getComputedStyle|overlay/"],["script","/Popunder|Banner/"],["script","return a.split"],["script","/popundersPerIP|adserverDomain|wpadmngr/"],["script","==\"]"],["script","ads-blocked"],["script","#adbd"],["script","AdBl"],["script","/adblock|Cuba|noadb|popundersPerIP/i"],["script","/adserverDomain|ai_cookie/"],["script","/adsBlocked|\"popundersPerIP\"/"],["script","ab.php"],["script","wpquads_adblocker_check"],["script","__adblocker"],["script","/alert|brave|blocker/i"],["script","/ai_|eval|Google/"],["script","/delete window|popundersPerIP|FingerprintJS|adserverDomain|globalThis;break;case|ai_adb|adContainer/"],["script","/eval|adb/i"],["script","catcher"],["script","/setADBFlag|cRAds|\\;break\\;case|adManager|const popup/"],["script","/isAdBlockActive|WebAssembly/"],["script","videoList"],["script","freestar"],["script","/admiral/i"],["script","self.loadPW"],["script","onload"],["script","/andbox|adBlock|data-zone|histats|contextmenu|ConsoleBan/"],["script","closePlayer"],["script","/banner/i"],["script","_0x"],["script","destroyContent"],["script","advanced_ads_check_adblocker"],["script","/dismissAdBlock|533092QTEErr/"],["script","/bait|adblock/i"],["script","debugger"],["script","decodeURIComponent"],["script","adblock_popup"],["script","MutationObserver"],["script","ad-gate"],["script","randPrefix"],["script",":visible"],["script","Datafadace"],["script","/popunder/i"],["script","adConfig"],["script","enable_ad_block_detector"],["script","/FingerprintJS|Adcash/"],["script","/const ads/i"],["#text","adinserter"],["script",".innerWidth"],["script","AD_URL"],["script","/join\\(\\'\\'\\)/"],["script","/join\\(\\\"\\\"\\)/"],["script","api.dataunlocker.com"],["script","/^Function\\(\\\"/"],["script","vglnk"],["script","/detect|FingerprintJS/"],["script","/RegExp\\(\\'/","condition","RegExp"],["script","sendFakeRequest"]];
const hostnamesMap = new Map([["www.youtube.com",0],["poophq.com",1],["veev.to",1],["faqwiki.*",2],["gameplayneo.com",2],["snapwordz.com",2],["toolxox.com",2],["rl6mans.com",2],["im9.eu",2],["marinetraffic.live",2],["nontonx.com",3],["embed.wcostream.com",4],["client.falixnodes.net",5],["omuzaani.me",6],["pandadoc.com",7],["web.de",8],["skidrowreloaded.com",[9,66]],["1337x.*",[9,66]],["1stream.eu",9],["4kwebplay.xyz",9],["alldownplay.xyz",9],["anime4i.vip",9],["antennasports.ru",[9,72]],["asiaflix.in",9],["boxingstream.me",9],["buffstreams.app",9],["claplivehdplay.ru",9],["cracksports.me",[9,19]],["cricstream.me",9],["cricstreams.re",[9,19]],["dartsstreams.com",9],["dl-protect.link",9],["eurekaddl.baby",9],["euro2024direct.ru",9],["ext.to",9],["extrem-down.*",9],["extreme-down.*",9],["eztv.*",9],["eztvx.to",9],["f1box.me",9],["filecrypt.cc",9],["flix-wave.*",9],["flixrave.me",9],["golfstreams.me",9],["hikaritv.xyz",9],["ianimes.one",9],["istreameast.app",9],["jointexploit.net",[9,66]],["kenitv.me",[9,19]],["lewblivehdplay.ru",[9,217]],["mediacast.click",9],["mixdrop.*",[9,66]],["mlbbite.net",9],["mlbstreams.ai",9],["motogpstream.me",9],["nbabox.me",9],["nflbite.com",9],["nflbox.me",9],["nhlbox.me",9],["ogladaj.in",9],["playcast.click",9],["playoffsstream.com",9],["qatarstreams.me",[9,19]],["qqwebplay.xyz",[9,217]],["reidoscanais.life",9],["rnbastreams.com",9],["rugbystreams.me",9],["sanet.*",9],["socceronline.me",9],["soccerworldcup.me",[9,19]],["sportshd.*",9],["sportzonline.si",9],["streamed.su",9],["sushiscan.net",9],["topstreams.info",9],["totalsportek.to",9],["tvableon.me",[9,19]],["vecloud.eu",9],["vibestreams.*",9],["vipstand.pm",9],["webcamrips.to",9],["worldsports.me",9],["x1337x.*",9],["zone-telechargement.*",9],["720pstream.*",[9,72]],["embedsports.me",[9,108]],["embedstream.me",[9,19,66,72,108]],["reliabletv.me",[9,108]],["topembed.pw",[9,74,217]],["crackstreamer.net",9],["vidsrc.*",[9,19,72]],["vidco.pro",[9,72]],["freestreams-live.*>>",9],["moviepilot.de",[10,62]],["userupload.*",11],["cinedesi.in",11],["turkedebiyati.org",11],["intro-hd.net",11],["monacomatin.mc",11],["nodo313.net",11],["mhdtvsports.*",[11,36]],["hesgoal-tv.io",11],["hesgoal-vip.io",11],["earn.punjabworks.com",11],["mahajobwala.in",11],["solewe.com",11],["panel.play.hosting",11],["total-sportek.to",11],["hesgoal-vip.to",11],["shoot-yalla.me",11],["shoot-yalla-tv.live",11],["pahe.*",[12,66,74]],["soap2day.*",12],["yts.mx",13],["hqq.*",14],["waaw.*",14],["pixhost.*",15],["vipbox.*",16],["telerium.*",17],["apex2nova.com",17],["hoca5.com",17],["germancarforum.com",18],["cybercityhelp.in",18],["innateblogger.com",18],["omeuemprego.online",18],["negyzetmeterarak.hu",18],["viprow.*",[19,66,72]],["bluemediadownload.*",19],["bluemediafile.*",19],["bluemedialink.*",19],["bluemediastorage.*",19],["bluemediaurls.*",19],["urlbluemedia.*",19],["bowfile.com",19],["cloudvideo.tv",[19,72]],["cloudvideotv.*",[19,72]],["coloredmanga.com",19],["exeo.app",19],["hiphopa.net",[19,66]],["megaup.net",19],["olympicstreams.co",[19,72]],["tv247.us",[19,66]],["uploadhaven.com",19],["userscloud.com",[19,72]],["streamnoads.com",[19,66,72,100]],["neodrive.xyz",19],["dutchycorp.*",20],["faucet.ovh",20],["mmacore.tv",21],["javtiful.com",[21,66]],["nxbrew.net",21],["brawlify.com",21],["oko.sh",22],["variety.com",[23,85]],["gameskinny.com",23],["deadline.com",[23,85]],["mlive.com",[23,85]],["washingtonpost.com",24],["gosexpod.com",25],["sexo5k.com",26],["truyen-hentai.com",26],["beinmatch.*",[27,66]],["theshedend.com",28],["cybermania.ws",28],["zeroupload.com",28],["streamvid.net",[28,66]],["securenetsystems.net",28],["miniwebtool.com",28],["bchtechnologies.com",28],["eracast.cc",28],["flatai.org",28],["leeapk.com",28],["spiegel.de",29],["jacquieetmichel.net",30],["hausbau-forum.de",31],["althub.club",31],["kiemlua.com",31],["doujindesu.*",32],["atlasstudiousa.com",32],["51bonusrummy.in",[32,75]],["tackledsoul.com",33],["adrino1.bonloan.xyz",33],["vi-music.app",33],["instanders.app",33],["rokni.xyz",33],["keedabankingnews.com",33],["sampledrive.org",[33,78]],["windroid777.com",33],["z80ne.com",33],["tea-coffee.net",34],["spatsify.com",34],["newedutopics.com",34],["getviralreach.in",34],["edukaroo.com",34],["funkeypagali.com",34],["careersides.com",34],["nayisahara.com",34],["wikifilmia.com",34],["infinityskull.com",34],["viewmyknowledge.com",34],["iisfvirtual.in",34],["starxinvestor.com",34],["jkssbalerts.com",34],["imagereviser.com",35],["veganab.co",36],["camdigest.com",36],["learnmany.in",36],["amanguides.com",[36,42]],["highkeyfinance.com",[36,42]],["appkamods.com",36],["techacode.com",36],["djqunjab.in",36],["downfile.site",36],["expertvn.com",36],["trangchu.news",36],["shemaleraw.com",36],["thecustomrom.com",36],["wemove-charity.org",36],["nulleb.com",36],["snlookup.com",36],["bingotingo.com",36],["ghior.com",36],["3dmili.com",36],["karanpc.com",36],["plc247.com",36],["apkdelisi.net",36],["freepasses.org",36],["poplinks.*",[36,46]],["tomarnarede.pt",36],["basketballbuzz.ca",36],["dribbblegraphics.com",36],["kemiox.com",36],["teksnologi.com",36],["bharathwick.com",36],["descargaspcpro.net",36],["dx-tv.com",[36,66]],["rt3dmodels.com",36],["plc4me.com",36],["blisseyhusbands.com",36],["mhdsports.*",36],["mhdsportstv.*",36],["mhdtvworld.*",36],["mhdtvmax.*",36],["mhdstream.*",36],["madaradex.org",36],["trigonevo.com",36],["franceprefecture.fr",36],["jazbaat.in",36],["aipebel.com",36],["audiotools.blog",36],["embdproxy.xyz",36],["fc-lc.*",37],["jobzhub.store",38],["fitdynamos.com",38],["labgame.io",38],["kenzo-flowertag.com",39],["mdn.lol",39],["btcbitco.in",40],["btcsatoshi.net",40],["cempakajaya.com",40],["crypto4yu.com",40],["manofadan.com",40],["readbitcoin.org",40],["wiour.com",40],["coin-free.com",[40,66]],["tremamnon.com",40],["bitsmagic.fun",40],["ourcoincash.xyz",40],["aylink.co",41],["sugarona.com",42],["nishankhatri.xyz",42],["cety.app",43],["exe-urls.com",43],["exego.app",43],["cutlink.net",43],["cutyurls.com",43],["cutty.app",43],["cutnet.net",43],["jixo.online",43],["ios.codevn.net",43],["tinys.click",44],["loan.creditsgoal.com",44],["rupyaworld.com",44],["vahantoday.com",44],["techawaaz.in",44],["loan.bgmi32bitapk.in",44],["formyanime.com",44],["gsm-solution.com",44],["h-donghua.com",44],["hindisubbedacademy.com",44],["hm4tech.info",44],["mydverse.*",44],["panelprograms.blogspot.com",44],["ripexbooster.xyz",44],["serial4.com",44],["tutorgaming.com",44],["unblockedgamesgplus.gitlab.io",44],["everydaytechvams.com",44],["dipsnp.com",44],["cccam4sat.com",44],["diendancauduong.com",44],["stitichsports.com",44],["aiimgvlog.fun",45],["appsbull.com",46],["diudemy.com",46],["maqal360.com",46],["androjungle.com",46],["bookszone.in",46],["shortix.co",46],["makefreecallsonline.com",46],["msonglyrics.com",46],["app-sorteos.com",46],["bokugents.com",46],["client.pylexnodes.net",46],["btvplus.bg",46],["listar-mc.net",46],["coingraph.us",47],["impact24.us",47],["iconicblogger.com",48],["auto-crypto.click",48],["tpi.li",49],["shrinkme.*",50],["shrinke.*",50],["mrproblogger.com",50],["themezon.net",50],["smutty.com",50],["e-sushi.fr",50],["gayforfans.com",50],["freeadultcomix.com",50],["down.dataaps.com",50],["filmweb.pl",[50,190]],["livecamrips.*",50],["safetxt.net",50],["filespayouts.com",50],["atglinks.com",51],["kbconlinegame.com",52],["hamrojaagir.com",52],["odijob.com",52],["stfly.biz",53],["airevue.net",53],["atravan.net",53],["cdn1.site",[53,66]],["simana.online",54],["fooak.com",54],["joktop.com",54],["evernia.site",54],["falpus.com",54],["rfiql.com",55],["gujjukhabar.in",55],["smartfeecalculator.com",55],["djxmaza.in",55],["thecubexguide.com",55],["jytechs.in",55],["financacerta.com",56],["encurtads.net",56],["mastkhabre.com",57],["weshare.is",58],["vplink.in",59],["3dsfree.org",60],["up4load.com",61],["alpin.de",62],["boersennews.de",62],["chefkoch.de",62],["chip.de",62],["clever-tanken.de",62],["desired.de",62],["donnerwetter.de",62],["fanfiktion.de",62],["focus.de",62],["formel1.de",62],["frustfrei-lernen.de",62],["gewinnspiele.tv",62],["giga.de",62],["gut-erklaert.de",62],["kino.de",62],["messen.de",62],["nickles.de",62],["nordbayern.de",62],["spielfilm.de",62],["teltarif.de",[62,63]],["unsere-helden.com",62],["weltfussball.at",62],["watson.de",62],["mactechnews.de",62],["sport1.de",62],["welt.de",62],["sport.de",62],["allthingsvegas.com",64],["100percentfedup.com",64],["beforeitsnews.com",64],["concomber.com",64],["conservativefiringline.com",64],["dailylol.com",64],["funnyand.com",64],["letocard.fr",64],["mamieastuce.com",64],["meilleurpronostic.fr",64],["patriotnationpress.com",64],["toptenz.net",64],["vitamiiin.com",64],["writerscafe.org",64],["populist.press",64],["dailytruthreport.com",64],["livinggospeldaily.com",64],["first-names-meanings.com",64],["welovetrump.com",64],["thehayride.com",64],["thelibertydaily.com",64],["thepoke.co.uk",64],["thepolitistick.com",64],["theblacksphere.net",64],["shark-tank.com",64],["naturalblaze.com",64],["greatamericanrepublic.com",64],["dailysurge.com",64],["truthlion.com",64],["flagandcross.com",64],["westword.com",64],["republicbrief.com",64],["freedomfirstnetwork.com",64],["phoenixnewtimes.com",64],["designbump.com",64],["clashdaily.com",64],["madworldnews.com",64],["reviveusa.com",64],["sonsoflibertymedia.com",64],["thedesigninspiration.com",64],["videogamesblogger.com",64],["protrumpnews.com",64],["thepalmierireport.com",64],["kresy.pl",64],["thepatriotjournal.com",64],["thegatewaypundit.com",64],["wltreport.com",64],["miaminewtimes.com",64],["politicalsignal.com",64],["rightwingnews.com",64],["bigleaguepolitics.com",64],["comicallyincorrect.com",64],["upornia.com",65],["mexa.sh",66],["123-movies.*",66],["123movieshd.*",66],["123movieshub.*",66],["123moviesme.*",66],["1337x.ninjaproxy1.com",66],["1bit.space",66],["1bitspace.com",66],["1stream.*",66],["1tamilmv.*",66],["2ddl.*",66],["2umovies.*",66],["3dporndude.com",66],["3hiidude.*",66],["4archive.org",66],["4chanarchives.com",66],["4horlover.com",66],["4stream.*",66],["560pmovie.com",66],["5movies.*",66],["7hitmovies.*",66],["85videos.com",66],["9xmovie.*",66],["aagmaal.*",[66,72]],["acefile.co",66],["actusports.eu",66],["adblockeronstape.*",[66,100]],["adblockeronstreamtape.*",66],["adblockplustape.*",[66,100]],["adblockstreamtape.*",[66,100]],["adblockstrtape.*",[66,100]],["adblockstrtech.*",[66,100]],["adblocktape.*",[66,100]],["adclickersbot.com",66],["adcorto.*",66],["adricami.com",66],["adslink.pw",[66,69]],["adultstvlive.com",66],["adz7short.space",66],["aeblender.com",66],["affordwonder.net",66],["ahdafnews.blogspot.com",66],["aiblog.tv",[66,75]],["ak47sports.com",66],["akuma.moe",66],["alexsports.*",[66,255]],["alexsportss.*",66],["alexsportz.*",66],["allplayer.tk",66],["amateurblog.tv",[66,75]],["androidadult.com",[66,244]],["anhsexjav.xyz",66],["anidl.org",66],["anime-loads.org",66],["animeblkom.net",66],["animefire.plus",66],["animelek.me",66],["animepahe.*",66],["animesanka.*",66],["animesorionvip.net",66],["animespire.net",66],["animestotais.xyz",66],["animeyt.es",66],["animixplay.*",66],["aniplay.*",66],["anroll.net",66],["antiadtape.*",[66,100]],["anymoviess.xyz",66],["aotonline.org",66],["asenshu.com",66],["asialiveaction.com",66],["asianclipdedhd.net",66],["asianclub.*",66],["ask4movie.*",66],["askim-bg.com",66],["assistirtvonlinebr.net",66],["asumsikedaishop.com",66],["atomixhq.*",[66,72]],["atomohd.*",66],["avcrempie.com",66],["avseesee.com",66],["gettapeads.com",[66,100]],["bajarjuegospcgratis.com",66],["balkanteka.net",66],["beastvid.tv",66],["belowporn.com",66],["bestgirlsexy.com",66],["bestnhl.com",66],["bestporncomix.com",66],["bhaai.*",66],["bigwarp.*",66],["bikinbayi.com",66],["bikinitryon.net",66],["birdurls.com",66],["bitsearch.to",66],["blackcockadventure.com",66],["blackcockchurch.org",66],["blackporncrazy.com",66],["blizzboygames.net",66],["blizzpaste.com",66],["blkom.com",66],["blog-peliculas.com",66],["blogtrabalhista.com",66],["blurayufr.*",66],["bobsvagene.club",66],["bokep.im",66],["bokep.top",66],["bokepnya.com",66],["bollyflix.cards",66],["boyfuck.me",66],["brilian-news.id",66],["brupload.net",66],["buffstreams.*",66],["buzter.xyz",66],["caitlin.top",66],["camchickscaps.com",66],["camgirls.casa",66],["canalesportivo.*",66],["cashurl.in",66],["ccurl.net",[66,72]],["charexempire.com",66],["cizgivedizi.com",66],["clickndownload.*",66],["clicknupload.*",[66,74]],["clik.pw",66],["coins100s.fun",66],["comohoy.com",66],["coolcast2.com",66],["cordneutral.net",66],["countylocalnews.com",66],["cpmlink.net",66],["crackstreamshd.click",66],["crespomods.com",66],["crisanimex.com",66],["crunchyscan.fr",66],["cuevana3.fan",66],["cuevana3hd.com",66],["cumception.com",66],["cutpaid.com",66],["daddylive.*",[66,72,215]],["daddylivehd.*",[66,72]],["daddylivestream.com",[66,215]],["dailyuploads.net",66],["darkmahou.org",66],["datawav.club",66],["daughtertraining.com",66],["ddrmovies.*",66],["deepgoretube.site",66],["deltabit.co",66],["deporte-libre.top",66],["depvailon.com",66],["derleta.com",66],["desiremovies.*",66],["desivdo.com",66],["desixx.net",66],["detikkebumen.com",66],["deutschepornos.me",66],["devlib.*",66],["diasoft.xyz",66],["dipelis.junctionjive.co.uk",66],["directupload.net",66],["divxtotal.*",66],["divxtotal1.*",66],["dixva.com",66],["djmaza.my",66],["dlhd.*",[66,215]],["doctormalay.com",66],["dofusports.xyz",66],["doods.cam",66],["doodskin.lat",66],["downloadrips.com",66],["downvod.com",66],["dphunters.mom",66],["dragontranslation.com",66],["dvdfullestrenos.com",66],["dvdplay.*",[66,72]],["ebookbb.com",66],["ebookhunter.net",66],["egyanime.com",66],["egygost.com",66],["ekasiwap.com",66],["electro-torrent.pl",66],["elixx.*",66],["elrefugiodelpirata.com",66],["enjoy4k.*",66],["eplayer.click",66],["erovoice.us",66],["eroxxx.us",66],["estrenosdoramas.net",66],["estrenosflix.*",66],["estrenosflux.*",66],["estrenosgo.*",66],["everia.club",66],["everythinginherenet.blogspot.com",66],["extratorrent.st",66],["extremotvplay.com",66],["f1stream.*",66],["fapptime.com",66],["faucethero.com",66],["favoyeurtube.net",66],["fbstream.*",66],["fc2db.com",66],["femdom-joi.com",[66,75]],["fenixsite.net",66],["file4go.*",66],["filegram.to",[66,69,75]],["fileone.tv",66],["film1k.com",66],["filmeonline2023.net",66],["filmesonlinex.org",66],["filmesonlinexhd.biz",66],["filmisub.cc",66],["filmnudes.com",66],["filmovitica.com",66],["filmymaza.blogspot.com",66],["filmyzilla.*",[66,72]],["filthy.family",66],["findav.*",66],["findporn.*",66],["flickzap.com",66],["flixmaza.*",66],["flizmovies.*",66],["flostreams.xyz",66],["flyfaucet.com",66],["footyhunter.lol",66],["forex-trnd.com",66],["forumchat.club",66],["forumlovers.club",66],["freeomovie.co.in",66],["freeomovie.to",66],["freeporncomic.net",66],["freepornhdonlinegay.com",66],["freeproxy.io",66],["freeshot.live",66],["freetvsports.*",66],["freeuse.me",66],["freeusexporn.com",66],["fsharetv.cc",66],["fsicomics.com",66],["fullymaza.*",66],["g-porno.com",66],["g3g.*",66],["galinhasamurai.com",66],["gamepcfull.com",66],["gamesmountain.com",66],["gamesrepacks.com",66],["gamingguru.fr",66],["gamovideo.com",66],["garota.cf",66],["gaydelicious.com",66],["gayfor.us",66],["gaypornhdfree.com",66],["gaypornhot.com",66],["gaypornmasters.com",66],["gaysex69.net",66],["gemstreams.com",66],["get-to.link",66],["girlscanner.org",66],["giurgiuveanul.ro",66],["gledajcrtace.xyz",66],["gocast2.com",66],["gomo.to",66],["gostosa.cf",66],["gotxx.*",66],["grantorrent.*",66],["gratispaste.com",66],["gravureblog.tv",[66,75]],["gupload.xyz",66],["haho.moe",66],["hayhd.net",66],["hdmoviesfair.*",[66,72]],["hdmoviesflix.*",66],["hdpornflix.com",66],["hdsaprevodom.com",66],["hdstreamss.club",66],["hentaiporno.xxx",66],["hentais.tube",66],["hentaistream.co",66],["hentaitk.net",66],["hentaitube.online",66],["hentaiworld.tv",66],["hesgoal.tv",66],["hexupload.net",66],["hhkungfu.tv",66],["highlanderhelp.com",66],["hiidudemoviez.*",66],["hindimovies.to",[66,72]],["hindimoviestv.com",66],["hiperdex.com",66],["hispasexy.org",66],["hitomi.la",66],["hitprn.com",66],["hivflix.*",66],["hoca4u.com",66],["hollymoviehd.cc",66],["hoodsite.com",66],["hopepaste.download",66],["hornylips.com",66],["hotgranny.live",66],["hotmama.live",66],["hqcelebcorner.net",66],["huren.best",66],["hwnaturkya.com",[66,72]],["hxfile.co",[66,72]],["igfap.com",66],["iklandb.com",66],["illink.net",66],["imgsen.*",66],["imgsex.xyz",66],["imgsto.*",66],["imgtraffic.com",66],["imx.to",66],["incest.*",66],["incestflix.*",66],["influencersgonewild.org",66],["infosgj.free.fr",66],["investnewsbrazil.com",66],["itdmusics.com",66],["itopmusic.*",66],["itsuseful.site",66],["itunesfre.com",66],["iwatchfriendsonline.net",[66,152]],["japangaysex.com",66],["jav-noni.cc",66],["javboys.tv",66],["javcl.com",66],["jav-coco.com",66],["javhay.net",66],["javhun.com",66],["javleak.com",66],["javmost.*",66],["javporn.best",66],["javsek.net",66],["javsex.to",66],["jimdofree.com",66],["jiofiles.org",66],["jorpetz.com",66],["jp-films.com",66],["jpop80ss3.blogspot.com",66],["jpopsingles.eu",[66,195]],["jrants.com",[66,81]],["justfullporn.net",66],["kantotflix.net",66],["kaplog.com",66],["kasiporn.com",66],["keeplinks.*",66],["keepvid.*",66],["keralahd.*",66],["khatrimazaful.*",66],["khatrimazafull.*",[66,75]],["kimochi.info",66],["kimochi.tv",66],["kinemania.tv",66],["kissasian.*",66],["kolnovel.site",66],["koltry.life",66],["konstantinova.net",66],["koora-online.live",66],["kunmanga.com",[66,72]],["kwithsub.com",66],["lat69.me",66],["latinblog.tv",[66,75]],["latinomegahd.net",66],["leechall.*",66],["leechpremium.link",66],["legendas.dev",66],["legendei.net",66],["lighterlegend.com",66],["linclik.com",66],["linkebr.com",66],["linkrex.net",66],["linkshorts.*",66],["lulu.st",66],["lulustream.com",[66,74]],["lulustream.live",66],["luluvdo.com",66],["luluvdoo.com",66],["mangaweb.xyz",66],["mangovideo.*",66],["masahub.com",66],["masahub.net",66],["masaporn.*",66],["maturegrannyfuck.com",66],["mdfx9dc8n.net",66],["mdy48tn97.com",66],["mediapemersatubangsa.com",66],["mega-mkv.com",66],["megapastes.com",66],["megapornpics.com",66],["messitv.net",66],["meusanimes.net",66],["milfmoza.com",66],["milfnut.*",66],["milfzr.com",66],["millionscast.com",66],["mimaletamusical.blogspot.com",66],["miniurl.*",66],["mirrorace.*",66],["mitly.us",66],["mixdroop.*",66],["mixiporn.fun",66],["miztv.top",66],["mkv-pastes.com",66],["mkvcage.*",66],["mlbstream.*",66],["mlsbd.*",66],["mmsbee.*",66],["monaskuliner.ac.id",66],["moredesi.com",66],["motogpstream.*",66],["moutogami.com",66],["movgotv.net",66],["movi.pk",66],["movieplex.*",66],["movierulzlink.*",66],["movies123.*",[66,75]],["moviesflix.*",66],["moviesmeta.*",66],["moviesmod.com.pl",66],["moviessources.*",66],["moviesverse.*",66],["movieswbb.com",66],["moviewatch.com.pk",66],["moviezwaphd.*",66],["mp4upload.com",66],["mrskin.live",66],["mrunblock.*",66],["multicanaistv.com",66],["mundowuxia.com",66],["multicanais.*",66],["myeasymusic.ir",66],["myonvideo.com",66],["myyouporn.com",66],["mzansifun.com",66],["naughtypiss.com",66],["nbastream.*",66],["nekopoi.*",[66,75]],["netfapx.com",66],["netfuck.net",66],["new-fs.eu",66],["newmovierulz.*",66],["newtorrentgame.com",66],["neymartv.net",66],["nflstream.*",66],["nflstreams.me",66],["nhlstream.*",66],["nicekkk.com",66],["nicesss.com",66],["nlegs.com",66],["noblocktape.*",[66,100]],["nocensor.*",66],["noni-jav.com",66],["notformembersonly.com",66],["novamovie.net",66],["novelpdf.xyz",66],["novelssites.com",[66,72]],["novelup.top",66],["nsfwr34.com",66],["nu6i-bg-net.com",66],["nudebabesin3d.com",66],["nzbstars.com",66],["o2tvseries.com",66],["ohjav.com",66],["ojearnovelas.com",66],["okanime.xyz",66],["olweb.tv",66],["olympusbiblioteca.site",66],["on9.stream",66],["onepiece-mangaonline.com",66],["onifile.com",66],["onionstream.live",66],["onlinesaprevodom.net",66],["onlyfams.*",66],["onlyfullporn.video",66],["onplustv.live",66],["originporn.com",66],["ouo.*",66],["ovagames.com",66],["pagalworld.cc",66],["pastemytxt.com",66],["payskip.org",66],["pctfenix.*",[66,72]],["pctnew.*",[66,72]],["peeplink.in",66],["peliculas24.*",66],["peliculasmx.net",66],["pelisflix20.*",66],["pelisplus.*",66],["pelisxporno.net",66],["pencarian.link",66],["pendidikandasar.net",66],["pervertgirlsvideos.com",66],["pervyvideos.com",66],["phim12h.com",66],["picdollar.com",66],["picsxxxporn.com",66],["pinayscandalz.com",66],["pinkueiga.net",66],["piratebay.*",66],["piratefast.xyz",66],["piratehaven.xyz",66],["pirateiro.com",66],["playtube.co.za",66],["plugintorrent.com",66],["plyjam.*",66],["plylive.*",66],["plyvdo.*",66],["pmvzone.com",66],["porndish.com",66],["pornez.net",66],["pornfetishbdsm.com",66],["pornfits.com",66],["pornhd720p.com",66],["pornhoarder.*",[66,236]],["pornobr.club",66],["pornobr.ninja",66],["pornodominicano.net",66],["pornofaps.com",66],["pornoflux.com",66],["pornotorrent.com.br",66],["pornredit.com",66],["pornstarsyfamosas.es",66],["pornstreams.co",66],["porntn.com",66],["pornxbit.com",66],["pornxday.com",66],["portaldasnovinhas.shop",66],["portugues-fcr.blogspot.com",66],["poseyoung.com",66],["pover.org",66],["prbay.*",66],["projectfreetv.*",66],["projeihale.com",66],["proxybit.*",66],["proxyninja.org",66],["psarips.*",66],["pubfilmz.com",66],["publicsexamateurs.com",66],["punanihub.com",66],["pxxbay.com",66],["qiqitvx84.shop",66],["r18.best",66],["racaty.*",66],["ragnaru.net",66],["rapbeh.net",66],["rapelust.com",66],["rapload.org",66],["read-onepiece.net",66],["readhunters.xyz",66],["remaxhd.*",66],["reshare.pm",66],["retro-fucking.com",66],["retrotv.org",66],["rintor.*",66],["rnbxclusive.*",66],["rnbxclusive0.*",66],["rnbxclusive1.*",66],["robaldowns.com",66],["rockdilla.com",66],["rojadirecta.*",66],["rojadirectaenvivo.*",66],["rojitadirecta.blogspot.com",66],["romancetv.site",66],["rsoccerlink.site",66],["rugbystreams.*",66],["rule34.club",66],["rule34hentai.net",66],["rumahbokep-id.com",66],["sadisflix.*",66],["safego.cc",66],["safetxt.*",66],["sakurafile.com",66],["samax63.lol",66],["sambalpuristar.in",66],["savefiles.com",[66,69]],["scat.gold",66],["scatfap.com",66],["scatkings.com",66],["sexdicted.com",66],["sexgay18.com",66],["sexiezpix.com",66],["sextubebbw.com",66],["sgpics.net",[66,75]],["shadowrangers.*",66],["shahed-4u.day",66],["shahee4u.cam",66],["shahhid4u.cam",66],["shahi4u.*",66],["shahid4u.*",66],["shahid4u1.*",66],["shahid4uu.*",66],["shahiid-anime.net",66],["shaid4u.day",66],["shavetape.*",66],["shemale6.com",66],["shemalegape.net",[66,68]],["shid4u.*",66],["shinden.pl",66],["short.es",66],["shortearn.*",66],["shorten.*",66],["shorttey.*",66],["shortzzy.*",66],["sideplusleaks.net",66],["silverblog.tv",[66,75]],["silverpic.com",66],["sinsitio.site",66],["skidrowcpy.com",66],["skymovieshd.*",66],["slut.mom",66],["smallencode.me",66],["smoner.com",66],["smplace.com",66],["socceron.name",66],["socceronline.*",[66,72]],["socialblog.tv",[66,75]],["softairbay.com",66],["softarchive.*",66],["sokobj.com",66],["songsio.com",66],["souexatasmais.com",66],["speedporn.net",[66,75]],["sportbar.live",66],["sports-stream.*",66],["sportstream1.cfd",66],["sporttuna.*",66],["sporttunatv.*",66],["srt.am",66],["srts.me",66],["sshhaa.*",66],["stapadblockuser.*",[66,100]],["stape.*",[66,100]],["stapewithadblock.*",66],["starblog.tv",[66,75]],["starmusiq.*",66],["stbemuiptv.com",66],["stockingfetishvideo.com",66],["strcloud.*",[66,100]],["stream.crichd.vip",66],["stream.lc",66],["stream25.xyz",66],["streamadblocker.*",[66,72,100]],["streamadblockplus.*",[66,100]],["streambee.to",66],["streambucket.net",66],["streamcdn.*",66],["streamcenter.pro",66],["streamers.watch",66],["streamgo.to",66],["streamhub.*",[66,72]],["streamingclic.com",66],["streamkiste.tv",66],["streamoupload.xyz",66],["streamservicehd.click",66],["streamsport.*",66],["streamta.*",[66,100]],["streamtape.*",[66,75,100]],["streamtapeadblockuser.*",[66,100]],["strikeout.*",[66,74]],["strtape.*",[66,100]],["strtapeadblock.*",[66,100]],["strtapeadblocker.*",[66,100]],["strtapewithadblock.*",66],["strtpe.*",[66,100]],["subtitleporn.com",66],["subtitles.cam",66],["suicidepics.com",66],["supertelevisionhd.com",66],["supexfeeds.com",66],["swatchseries.*",66],["swiftload.io",66],["swipebreed.net",66],["swzz.xyz",66],["sxnaar.com",66],["tabooflix.*",66],["taboosex.club",66],["tapeantiads.com",[66,100]],["tapeblocker.com",[66,100]],["tapenoads.com",[66,100]],["tapepops.com",[66,75,100]],["tapewithadblock.org",[66,100,295]],["teamos.xyz",66],["telegramgroups.xyz",66],["tempodeconhecer.blogs.sapo.pt",66],["tennisstreams.*",66],["tfp.is",66],["tgo-tv.co",[66,72]],["thaihotmodels.com",66],["theblueclit.com",66],["thebussybandit.com",66],["thedaddy.*",[66,215]],["thelastdisaster.vip",66],["themoviesflix.*",66],["thepiratebay.*",66],["thepiratebay0.org",66],["thepiratebay10.info",66],["thesexcloud.com",66],["thothub.today",66],["tightsexteens.com",66],["tlnovelas.net",66],["tmearn.*",66],["tojav.net",66],["tokusatsuindo.com",66],["tokyocafe.org",66],["toonanime.*",66],["top16.net",66],["topdrama.net",66],["topvideosgay.com",66],["torlock.*",66],["tormalayalam.*",66],["torrage.info",66],["torrents.vip",66],["torrentz2eu.*",66],["torrsexvid.com",66],["tpb-proxy.xyz",66],["trannyteca.com",66],["trendytalker.com",66],["tuktukcinma.com",66],["tumanga.net",66],["turbogvideos.com",66],["turboimagehost.com",66],["turbovid.me",66],["turkishseriestv.org",66],["turksub24.net",66],["tutele.sx",66],["tutelehd.*",66],["tv247us.live",66],["tvglobe.me",66],["tvpclive.com",66],["tvply.*",66],["tvs-widget.com",66],["tvseries.video",66],["u4m.*",66],["ucptt.com",66],["ufaucet.online",66],["ufcfight.online",66],["ufcstream.*",66],["ultrahorny.com",66],["ultraten.net",66],["unblocknow.*",66],["unblockweb.me",66],["underhentai.net",66],["uniqueten.net",66],["uns.bio",66],["upbaam.com",66],["uploadbuzz.*",66],["upstream.to",66],["upzur.com",66],["usagoals.*",66],["ustream.to",66],["valhallas.click",66],["valeriabelen.com",66],["vegamoviies.*",66],["verdragonball.online",66],["vexmoviex.*",66],["vfxmed.com",66],["vidclouds.*",66],["video.az",66],["videostreaming.rocks",66],["videowood.tv",66],["vidlox.*",66],["vidorg.net",66],["vidtapes.com",66],["vidz7.com",66],["vikistream.com",66],["vinovo.to",66],["vipboxtv.*",[66,72]],["vipleague.*",66],["viral.wf",66],["virpe.cc",66],["visifilmai.org",66],["viveseries.com",66],["vladrustov.sx",66],["volokit2.com",[66,72,215]],["vstorrent.org",66],["w4hd.com",66],["watch-series.*",66],["watchbrooklynnine-nine.com",66],["watchelementaryonline.com",66],["watchf1full.com",66],["watchfamilyguyonline.com",66],["watchkobestreams.info",66],["watchlostonline.net",66],["watchmmafull.com",66],["watchmodernfamilyonline.com",66],["watchmonkonline.com",66],["watchrulesofengagementonline.com",66],["watchseries.*",66],["webcamrips.com",66],["wincest.xyz",66],["wolverdon.fun",66],["wordcounter.icu",66],["worldmovies.store",66],["worldstreams.click",66],["wpdeployit.com",66],["wqstreams.tk",66],["wwwsct.com",66],["x18hub.com",66],["xanimeporn.com",66],["xblog.tv",[66,75]],["xclusivejams.*",66],["xmoviesforyou.*",66],["xn--verseriesespaollatino-obc.online",66],["xpornium.net",66],["xsober.com",66],["xvip.lat",66],["xxgasm.com",66],["xxvideoss.org",66],["xxx18.uno",66],["xxxdominicana.com",66],["xxxfree.watch",66],["xxxmax.net",66],["xxxwebdlxxx.top",66],["xxxxvideo.uno",66],["yabai.si",66],["yeshd.net",66],["youdbox.*",66],["youjax.com",66],["yourdailypornvideos.ws",66],["yourupload.com",66],["youswear.com",66],["ytmp3eu.*",66],["yts-subs.*",66],["yts.*",66],["ytstv.me",66],["yumeost.net",66],["zerion.cc",66],["zerocoin.top",66],["zitss.xyz",66],["zooqle.*",66],["zpaste.net",66],["md3b0j6hj.com",66],["mdzsmutpcvykb.net",66],["mixdrop21.net",66],["mixdropjmk.pw",66],["fastreams.com",66],["streamsoccer.site",66],["tntsports.store",66],["wowstreams.co",66],["pillowcase.su",67],["akaihentai.com",68],["cine-calidad.*",68],["fastpic.org",[68,75]],["forums.socialmediagirls.com",[68,75]],["javtsunami.com",68],["manwa.me",68],["monoschino2.com",68],["saradahentai.com",68],["sxyprn.*",68],["tabooporn.tv",68],["veryfreeporn.com",68],["x-video.tube",68],["pornoenspanish.es",68],["theporngod.com",68],["tabootube.to",68],["bebasbokep.online",69],["besthdgayporn.com",69],["bokepindo13.*",69],["dimensionalseduction.com",69],["drivenime.com",69],["erothots1.com",69],["javbobo.com",69],["javup.org",69],["kaliscan.*",69],["madouqu.com",69],["shemaleup.net",69],["transflix.net",69],["worthcrete.com",69],["x-x-x.video",[69,274]],["malluporno.com",70],["hentaihere.com",71],["player.smashy.stream",71],["player.smashystream.com",71],["11xmovies.*",[72,74]],["123movies.*",72],["123moviesla.*",72],["123movieweb.*",72],["2embed.*",72],["3kmovies.*",72],["720pflix.*",72],["7starhd.*",72],["9xflix.*",72],["9xmovies.*",72],["adsh.cc",72],["adshort.*",72],["afilmyhouse.blogspot.com",72],["ak.sv",72],["aliezstream.pro",[72,174]],["allmovieshub.*",72],["animesultra.net",72],["api.webs.moe",72],["apkmody.io",72],["asianplay.*",72],["atishmkv.*",72],["backfirstwo.site",72],["bflix.*",72],["crazyblog.in",72],["cricstream.*",72],["crictime.*",72],["cuervotv.me",72],["defienietlynotme.com",72],["divicast.com",72],["dood.*",[72,95]],["dooood.*",[72,95]],["egybest.*",72],["embedme.*",72],["embedpk.net",72],["esportivos.site",72],["extramovies.*",72],["faselhd.*",72],["faselhds.*",72],["faselhdwatch.*",72],["filemoon.*",72],["filemooon.*",72],["filmeserialeonline.org",72],["filmy.*",72],["filmyhit.*",72],["filmywap.*",72],["finfang.*",72],["flexyhit.com",72],["flixhq.*",72],["fmembed.cc",72],["fmoonembed.*",72],["fmovies.*",72],["focus4ca.com",72],["footybite.to",72],["foreverwallpapers.com",72],["french-streams.cc",72],["gdplayer.*",72],["gdrivelatinohd.net",72],["globalstreams.xyz",72],["gocast.pro",72],["godzcast.com",72],["goku.sx",72],["gomovies.*",72],["gowatchseries.*",72],["hdfungamezz.*",72],["hdmovies23.*",72],["hdtoday.to",72],["hellnaw.*",72],["hianime.to",72],["hinatasoul.com",72],["hindilinks4u.*",72],["hurawatch.*",72],["igg-games.com",72],["infinityscans.net",72],["jalshamoviezhd.*",72],["kaido.to",72],["kerapoxy.*",72],["linkshub.*",72],["livecricket.*",72],["livestreames.us",72],["locatedinfain.com",72],["mangareader.to",72],["maxstream.*",72],["mhdsport.*",72],["mkvcinemas.*",72],["moonembed.*",72],["moviekids.tv",72],["movies2watch.*",72],["moviesda9.co",72],["moviespapa.*",72],["mp4moviez.*",72],["mydownloadtube.*",72],["myflixertv.to",72],["myflixerz.to",72],["mylivestream.pro",[72,174]],["nowmetv.net",72],["nowsportstv.com",72],["nuroflix.*",72],["nxbrew.com",72],["o2tvseries.*",72],["o2tvseriesz.*",72],["oii.io",72],["paidshitforfree.com",72],["pepperlive.info",72],["pirlotv.*",72],["pkspeed.net",72],["playertv.net",72],["poscitech.*",72],["primewire.*",72],["redecanais.*",72],["rgeyyddl.*",72],["ronaldo7.pro",72],["roystream.com",72],["rssing.com",72],["s.to",72],["serienstream.*",72],["sflix.*",72],["shahed4u.*",72],["shaheed4u.*",72],["share.filesh.site",72],["sharkfish.xyz",72],["skidrowcodex.net",72],["smartermuver.com",72],["speedostream.*",72],["sportcast.*",72],["sportshub.fan",72],["sportskart.*",72],["stream4free.live",72],["streamingcommunity.*",[72,74,119]],["sulleiman.com",72],["tamilarasan.*",72],["tamilfreemp3songs.*",72],["tamilmobilemovies.in",72],["tamilprinthd.*",72],["tapeadsenjoyer.com",[72,75,100]],["tapeadvertisement.com",[72,100]],["tapelovesads.org",[72,100]],["thewatchseries.live",72],["tnmusic.in",72],["torrentdosfilmes.*",72],["totalsportek.*",72],["travelplanspro.com",72],["tubemate.*",72],["tusfiles.com",72],["tutlehd4.com",72],["twstalker.com",72],["uploadrar.*",72],["uqload.*",72],["vegamovie.*",72],["vid-guard.com",72],["vidcloud9.*",72],["vido.*",72],["vidoo.*",72],["vidsaver.net",72],["vidspeeds.com",72],["viralitytoday.com",72],["voiranime.stream",72],["vpcxz19p.xyz",72],["vudeo.*",72],["vumoo.*",72],["watchdoctorwhoonline.com",72],["watchomovies.*",[72,116]],["watchserie.online",72],["woxikon.in",72],["www-y2mate.com",72],["yesmovies.*",72],["ylink.bid",72],["z12z0vla.*",72],["zvision.link",72],["xn-----0b4asja7ccgu2b4b0gd0edbjm2jpa1b1e9zva7a0347s4da2797e8qri.xn--1ck2e1b",72],["kickassanime.*",73],["cinego.tv",74],["dokoembed.pw",74],["ev01.to",74],["fojik.*",74],["fstream365.com",74],["fzmovies.*",74],["linkz.*",74],["minoplres.xyz",74],["mostream.us",74],["moviedokan.*",74],["myflixer.*",74],["oii.la",74],["prmovies.*",74],["readcomiconline.li",74],["s3embtaku.pro",74],["sflix2.to",74],["sportshub.stream",74],["streamblasters.*",74],["topcinema.cam",74],["webxzplay.cfd",74],["zonatmo.com",74],["animesaturn.cx",74],["filecrypt.*",74],["hunterscomics.com",74],["aniwave.uk",74],["dojing.net",75],["fuckflix.click",75],["javsubindo.com",75],["krx18.com",75],["loadx.ws",75],["mangaforfree.com",75],["pornx.to",75],["savefiles.*",[75,257]],["shavetape.cash",75],["strcloud.club",75],["strcloud.site",75],["streampoi.com",75],["strmup.to",[75,174]],["up4stream.com",[75,116]],["ups2up.fun",[75,116]],["videq.stream",75],["xmegadrive.com",75],["rubystm.com",75],["rubyvid.com",75],["rubyvidhub.com",75],["stmruby.com",75],["streamruby.com",75],["kaa.to",76],["hyhd.org",77],["bi-girl.net",78],["ftuapps.*",78],["hentaiseason.com",78],["hoodtrendspredict.com",78],["marcialhub.xyz",78],["odiadance.com",78],["osteusfilmestuga.online",78],["ragnarokscanlation.opchapters.com",78],["showflix.*",78],["swordalada.org",78],["tvappapk.com",78],["twobluescans.com",[78,79]],["varnascan.xyz",78],["fcsnew.net",80],["bibliopanda.visblog.online",81],["hallofseries.com",81],["luciferdonghua.in",81],["toursetlist.com",81],["truyentranhfull.net",81],["fcportables.com",81],["repack-games.com",81],["ibooks.to",81],["blog.tangwudi.com",81],["filecatchers.com",81],["babaktv.com",81],["tablelifeblog.com",82],["thebeautysection.com",82],["thecurvyfashionista.com",82],["thefashionspot.com",82],["thegamescabin.com",82],["thenerdyme.com",82],["thenonconsumeradvocate.com",82],["theprudentgarden.com",82],["thethings.com",82],["timesnews.net",82],["topspeed.com",82],["toyotaklub.org.pl",82],["travelingformiles.com",82],["tutsnode.org",82],["viralviralvideos.com",82],["wannacomewith.com",82],["wimp.com",[82,85]],["windsorexpress.co.uk",82],["woojr.com",82],["worldoftravelswithkids.com",82],["worldsurfleague.com",82],["cheatsheet.com",83],["pwinsider.com",83],["c-span.org",84],["15min.lt",85],["247sports.com",85],["abc17news.com",85],["addictinggames.com",85],["agrodigital.com",85],["al.com",85],["aliontherunblog.com",85],["allaboutthetea.com",85],["allmovie.com",85],["allmusic.com",85],["allthingsthrifty.com",85],["amessagewithabottle.com",85],["arstechnica.com",85],["artforum.com",85],["artnews.com",85],["audiomack.com",85],["awkward.com",85],["barcablaugranes.com",85],["barnsleychronicle.com",85],["bethcakes.com",85],["betweenenglandandiowa.com",85],["bgr.com",85],["billboard.com",85],["blazersedge.com",85],["blogher.com",85],["blu-ray.com",85],["bluegraygal.com",85],["briefeguru.de",85],["brobible.com",85],["cagesideseats.com",85],["cbsnews.com",85],["cbssports.com",[85,262]],["celiacandthebeast.com",85],["chaptercheats.com",85],["cleveland.com",85],["clickondetroit.com",85],["commercialcompetentedigitale.ro",85],["crooksandliars.com",85],["dailydot.com",85],["dailykos.com",85],["dailyvoice.com",85],["danslescoulisses.com",85],["decider.com",85],["didyouknowfacts.com",85],["dogtime.com",85],["dpreview.com",85],["ebaumsworld.com",85],["egoallstars.com",85],["eldiariony.com",85],["fark.com",85],["femestella.com",85],["flickr.com",85],["fmradiofree.com",85],["forums.hfboards.com",85],["free-power-point-templates.com",85],["freeconvert.com",85],["frogsandsnailsandpuppydogtail.com",85],["funtasticlife.com",85],["fwmadebycarli.com",85],["golfdigest.com",85],["grunge.com",85],["gulflive.com",85],["hollywoodreporter.com",85],["homeglowdesign.com",85],["honeygirlsworld.com",85],["ibtimes.co.in",85],["imgur.com",85],["indiewire.com",85],["intouchweekly.com",85],["jasminemaria.com",85],["kens5.com",85],["kion546.com",85],["knowyourmeme.com",85],["last.fm",85],["lehighvalleylive.com",85],["lettyskitchen.com",85],["lifeandstylemag.com",85],["lifeinleggings.com",85],["lizzieinlace.com",85],["localnews8.com",85],["lonestarlive.com",85],["madeeveryday.com",85],["maidenhead-advertiser.co.uk",85],["mandatory.com",85],["mardomreport.net",85],["masslive.com",85],["melangery.com",85],["miamiherald.com",85],["mmamania.com",85],["momtastic.com",85],["mostlymorgan.com",85],["motherwellmag.com",85],["motorsport.com",85],["musicfeeds.com.au",85],["naszemiasto.pl",85],["nationalpost.com",85],["nationalreview.com",85],["nbcsports.com",85],["news.com.au",85],["ninersnation.com",85],["nj.com",85],["nordot.app",85],["nothingbutnewcastle.com",85],["nsjonline.com",85],["nypost.com",85],["observer.com",85],["ontvtonight.com",85],["oregonlive.com",85],["pagesix.com",85],["patheos.com",85],["pcbolsa.com",85],["pennlive.com",85],["pep.ph",[85,90]],["phillyvoice.com",85],["playstationlifestyle.net",85],["puckermom.com",85],["reelmama.com",85],["rlfans.com",85],["robbreport.com",85],["rollingstone.com",85],["royalmailchat.co.uk",85],["sandrarose.com",85],["sbnation.com",85],["silive.com",85],["sheknows.com",85],["sidereel.com",85],["smartworld.it",85],["sneakernews.com",85],["sourcingjournal.com",85],["soldionline.it",85],["sport-fm.gr",85],["sportico.com",85],["sportsgamblingpodcast.com",85],["spotofteadesigns.com",85],["ssnewstelegram.com",85],["stacysrandomthoughts.com",85],["stylecaster.com",85],["superherohype.com",85],["syracuse.com",85],["tastingtable.com",85],["techcrunch.com",85],["thecelticblog.com",[85,87]],["thedailymeal.com",85],["theflowspace.com",85],["themarysue.com",85],["thenerdstash.com",85],["tiermaker.com",85],["timesofisrael.com",85],["tiscali.cz",85],["tokfm.pl",85],["torontosun.com",85],["tvline.com",85],["usmagazine.com",85],["wallup.net",85],["wcnc.com",85],["weather.com",85],["worldstar.com",85],["worldstarhiphop.com",85],["wwd.com",85],["wzzm13.com",85],["yourcountdown.to",85],["automobile-catalog.com",[86,87]],["baseballchannel.jp",[86,87]],["forum.mobilism.me",86],["gbatemp.net",86],["gentosha-go.com",86],["hang.hu",86],["hoyme.jp",86],["motorbikecatalog.com",[86,87]],["sharemods.com",86],["wisevoter.com",86],["topstarnews.net",86],["islamicfinder.org",86],["secure-signup.net",86],["dramabeans.com",86],["dropgame.jp",[86,87]],["manta.com",86],["tportal.hr",86],["tvtropes.org",[86,287]],["convertcase.net",86],["oricon.co.jp",87],["uranai.nosv.org",87],["yakkun.com",87],["24sata.hr",87],["373news.com",87],["actugaming.net",87],["aerotrader.com",87],["alc.co.jp",87],["alfa.lt",87],["allthetests.com",87],["animanch.com",87],["aniroleplay.com",87],["apkmirror.com",[87,194]],["areaconnect.com",87],["as-web.jp",87],["atvtrader.com",87],["aucfree.com",87],["autoby.jp",87],["autoc-one.jp",87],["autofrage.net",87],["bab.la",87],["babla.*",87],["bien.hu",87],["bilis.lt",87],["boredpanda.com",87],["bunshun.jp",87],["calculatorsoup.com",87],["carscoops.com",87],["cesoirtv.com",87],["chanto.jp.net",87],["cinetrafic.fr",87],["cocokara-next.com",87],["collinsdictionary.com",87],["commercialtrucktrader.com",87],["computerfrage.net",87],["crosswordsolver.com",87],["cruciverba.it",87],["cults3d.com",87],["culturequizz.com",87],["cycletrader.com",87],["daily.co.jp",87],["dailynewshungary.com",87],["dallashoopsjournal.com",87],["dayspedia.com",87],["dictionary.cambridge.org",87],["dictionnaire.lerobert.com",87],["dnevno.hr",87],["dreamchance.net",87],["drweil.com",87],["dziennik.pl",87],["ecranlarge.com",87],["eigachannel.jp",87],["equipmenttrader.com",87],["etaplius.lt",87],["ev-times.com",87],["finanzfrage.net",87],["footballchannel.jp",87],["forsal.pl",87],["freemcserver.net",87],["futabanet.jp",87],["fxstreet-id.com",87],["fxstreet-vn.com",87],["fxstreet.*",87],["game8.jp",87],["games.arkadium.com",87],["gamewith.jp",87],["gardeningsoul.com",87],["gazetaprawna.pl",87],["gesundheitsfrage.net",87],["gifu-np.co.jp",87],["gigafile.nu",87],["globalrph.com",87],["golf-live.at",87],["grapee.jp",87],["gutefrage.net",87],["happymoments.lol",87],["hb-nippon.com",87],["heureka.cz",87],["hochi.news",87],["horairesdouverture24.fr",87],["hotcopper.co.nz",87],["hotcopper.com.au",87],["hvac-talk.com",87],["idokep.hu",87],["indiatimes.com",87],["infor.pl",87],["iza.ne.jp",87],["j-cast.com",87],["j-town.net",87],["j7p.jp",87],["jablickar.cz",87],["javatpoint.com",87],["jiji.com",87],["jikayosha.jp",87],["judgehype.com",87],["kinmaweb.jp",87],["km77.com",87],["kobe-journal.com",87],["kreuzwortraetsel.de",87],["kurashinista.jp",87],["kurashiru.com",87],["kyoteibiyori.com",87],["lacuarta.com",87],["laleggepertutti.it",87],["langenscheidt.com",87],["laposte.net",87],["lawyersgunsmoneyblog.com",87],["ldoceonline.com",87],["listentotaxman.com",87],["livenewschat.eu",87],["luremaga.jp",87],["mafab.hu",87],["mahjongchest.com",87],["mainichi.jp",87],["maketecheasier.com",[87,88]],["malaymail.com",87],["mamastar.jp",87],["mathplayzone.com",87],["meteo60.fr",87],["midhudsonnews.com",87],["minesweeperquest.com",87],["minkou.jp",87],["mmm.lt",87],["modhub.us",87],["modsfire.com",87],["moin.de",87],["motorradfrage.net",87],["motscroises.fr",87],["movie-locations.com",87],["muragon.com",87],["namemc.com",87],["nana-press.com",87],["natalie.mu",87],["nationaltoday.com",87],["nbadraft.net",87],["newatlas.com",[87,93,94]],["news.zerkalo.io",87],["newsinlevels.com",87],["newsweekjapan.jp",87],["niketalk.com",87],["nikkan-gendai.com",87],["nlab.itmedia.co.jp",87],["notebookcheck.*",87],["notebookcheck-cn.com",87],["notebookcheck-hu.com",87],["notebookcheck-ru.com",87],["notebookcheck-tr.com",87],["nouvelobs.com",87],["nyitvatartas24.hu",87],["oeffnungszeitenbuch.de",87],["onlineradiobox.com",87],["operawire.com",87],["optionsprofitcalculator.com",87],["oraridiapertura24.it",87],["oxfordlearnersdictionaries.com",87],["palabr.as",87],["pashplus.jp",87],["persoenlich.com",87],["petitfute.com",87],["play-games.com",87],["popdaily.com.tw",87],["powerpyx.com",87],["pptvhd36.com",87],["profitline.hu",87],["programme-tv.net",87],["puzzlegarage.com",87],["pwctrader.com",87],["quefaire.be",87],["radio-australia.org",87],["radio-osterreich.at",87],["raetsel-hilfe.de",87],["raider.io",87],["ranking.net",87],["raskakcija.lt",87],["references.be",87],["reisefrage.net",87],["relevantmagazine.com",87],["reptilesmagazine.com",87],["roleplayer.me",87],["rostercon.com",87],["samsungmagazine.eu",87],["sankei.com",87],["sanspo.com",87],["scribens.com",87],["scribens.fr",87],["si.com",87],["slashdot.org",87],["snowmobiletrader.com",87],["soccerdigestweb.com",87],["solitairehut.com",87],["sourceforge.net",87],["southhemitv.com",87],["sportalkorea.com",87],["sportlerfrage.net",87],["statecollege.com",87],["steamidfinder.com",87],["stocktwits.com",87],["sudokutable.com",87],["superhonda.com",87],["syosetu.com",87],["szamoldki.hu",87],["talkwithstranger.com",87],["tastesbetterfromscratch.com",87],["tbs.co.jp",87],["techdico.com",87],["the-crossword-solver.com",87],["thedigestweb.com",87],["thefirearmblog.com",87],["traicy.com",87],["transparentcalifornia.com",87],["transparentnevada.com",87],["trilltrill.jp",87],["tunebat.com",87],["tvtv.ca",87],["tvtv.us",87],["tweaktown.com",87],["twn.hu",87],["tyda.se",87],["ufret.jp",87],["universalis.fr",87],["uptodown.com",87],["uscreditcardguide.com",87],["verkaufsoffener-sonntag.com",87],["vimm.net",87],["wamgame.jp",87],["watchdocumentaries.com",87],["wattedoen.be",87],["webdesignledger.com",87],["weldingweb.com",87],["wetteronline.de",87],["wfmz.com",87],["wieistmeineip.*",87],["winfuture.de",87],["word-grabber.com",87],["worldjournal.com",87],["worldle.teuteuf.fr",87],["wort-suchen.de",87],["woxikon.*",87],["young-machine.com",87],["yugioh-starlight.com",87],["yutura.net",87],["zagreb.info",87],["zakzak.co.jp",87],["pons.com",87],["2chblog.jp",87],["2monkeys.jp",87],["46matome.net",87],["akb48glabo.com",87],["akb48matomemory.com",87],["alfalfalfa.com",87],["all-nationz.com",87],["anihatsu.com",87],["aqua2ch.net",87],["blog.esuteru.com",87],["blog.livedoor.jp",87],["blog.jp",87],["blogo.jp",87],["chaos2ch.com",87],["choco0202.work",87],["crx7601.com",87],["danseisama.com",87],["dareda.net",87],["digital-thread.com",87],["doorblog.jp",87],["exawarosu.net",87],["fgochaldeas.com",87],["football-2ch.com",87],["gekiyaku.com",87],["golog.jp",87],["hacchaka.net",87],["heartlife-matome.com",87],["liblo.jp",87],["fesoku.net",87],["fiveslot777.com",87],["gamejksokuhou.com",87],["girlsreport.net",87],["girlsvip-matome.com",87],["grasoku.com",87],["gundamlog.com",87],["honyaku-channel.net",87],["ikarishintou.com",87],["imas-cg.net",87],["imihu.net",87],["inutomo11.com",87],["itainews.com",87],["itaishinja.com",87],["jin115.com",87],["jisaka.com",87],["jnews1.com",87],["jumpsokuhou.com",87],["jyoseisama.com",87],["keyakizaka46matomemory.net",87],["kidan-m.com",87],["kijoden.com",87],["kijolariat.net",87],["kijolifehack.com",87],["kijomatomelog.com",87],["kijyokatu.com",87],["kijyomatome.com",87],["kijyomatome-ch.com",87],["kijyomita.com",87],["kirarafan.com",87],["kitimama-matome.net",87],["kitizawa.com",87],["konoyubitomare.jp",87],["kotaro269.com",87],["kyousoku.net",87],["ldblog.jp",87],["livedoor.biz",87],["livedoor.blog",87],["majikichi.com",87],["matacoco.com",87],["matomeblade.com",87],["matomelotte.com",87],["matometemitatta.com",87],["mojomojo-licarca.com",87],["morikinoko.com",87],["nandemo-uketori.com",87],["netatama.net",87],["news-buzz1.com",87],["news30over.com",87],["nishinippon.co.jp",87],["nmb48-mtm.com",87],["norisoku.com",87],["npb-news.com",87],["ocsoku.com",87],["okusama-kijyo.com",87],["onecall2ch.com",87],["onihimechan.com",87],["orusoku.com",87],["otakomu.jp",87],["otoko-honne.com",87],["oumaga-times.com",87],["outdoormatome.com",87],["pachinkopachisro.com",87],["paranormal-ch.com",87],["recosoku.com",87],["s2-log.com",87],["saikyo-jump.com",87],["shuraba-matome.com",87],["ske48matome.net",87],["squallchannel.com",87],["sukattojapan.com",87],["sumaburayasan.com",87],["sutekinakijo.com",87],["usi32.com",87],["uwakich.com",87],["uwakitaiken.com",87],["vault76.info",87],["vipnews.jp",87],["vippers.jp",87],["vipsister23.com",87],["vtubernews.jp",87],["watarukiti.com",87],["world-fusigi.net",87],["zakuzaku911.com",87],["zch-vip.com",87],["300cforums.com",87],["a5oc.com",87],["acuraworld.com",87],["airsoftsociety.com",87],["allpar.com",87],["aquaticplantcentral.com",87],["astraownersnetwork.co.uk",87],["avsforum.com",87],["babybmw.net",87],["beesource.com",87],["bimmerwerkz.com",87],["can-amforum.com",87],["canadianmoneyforum.com",87],["catfish1.com",87],["chevymalibuforum.com",87],["chinacarforums.com",87],["chihuahua-people.com",87],["coloradofans.com",87],["dairygoatinfo.com",87],["digitalhome.ca",87],["diychatroom.com",87],["fordescape.org",87],["fullsizebronco.com",87],["mazda3revolution.com",87],["mdxers.org",87],["mytractorforum.com",87],["odyclub.com",87],["rootzwiki.com",87],["skyscrapercity.com",87],["speypages.com",87],["techguy.org",87],["techsupportforum.com",87],["theakforum.net",87],["trailvoy.com",87],["vwvortex.com",87],["interfootball.co.kr",88],["a-ha.io",88],["cboard.net",88],["jjang0u.com",88],["joongdo.co.kr",88],["viva100.com",88],["tweaksforgeeks.com",88],["m.inven.co.kr",88],["mlbpark.donga.com",88],["meconomynews.com",88],["brandbrief.co.kr",88],["motorgraph.com",88],["bleepingcomputer.com",89],["pravda.com.ua",89],["ap7am.com",90],["cinema.com.my",90],["dolldivine.com",90],["giornalone.it",90],["iplocation.net",90],["jamaicajawapos.com",90],["jutarnji.hr",90],["kompasiana.com",90],["mediaindonesia.com",90],["niice-woker.com",90],["slobodnadalmacija.hr",90],["upmedia.mg",90],["mentalfloss.com",91],["wetter.com",92],["neowin.net",[93,94]],["razzball.com",[93,94]],["dnevnik.hr",94],["all3do.com",95],["d-s.io",95],["d0000d.com",95],["d000d.com",95],["d0o0d.com",95],["do0od.com",95],["do7go.com",95],["doods.*",95],["doodstream.*",95],["dooodster.com",95],["doply.net",95],["ds2play.com",95],["ds2video.com",95],["vidply.com",95],["vide0.net",95],["vvide0.com",95],["3minx.com",96],["555fap.com",96],["ai18.pics",96],["anime-jav.com",96],["blackwidof.org",96],["chinese-pics.com",96],["cn-av.com",96],["cnpics.org",96],["cnxx.me",96],["cosplay-xxx.com",96],["cosplay18.pics",96],["fc2ppv.stream",96],["fikfok.net",96],["gofile.download",96],["hentai-sub.com",96],["hentai4f.com",96],["hentaicovid.com",96],["hentaipig.com",96],["hentaixnx.com",96],["idol69.net",96],["javball.com",96],["javbee.*",96],["javring.com",96],["javsunday.com",96],["javtele.net",96],["kin8-av.com",96],["kin8-jav.com",96],["kr-av.com",96],["ovabee.com",96],["pig69.com",96],["porn-pig.com",96],["porn4f.org",96],["sweetie-fox.com",96],["xcamcovid.com",96],["xxpics.org",96],["hentaivost.fr",97],["jelonka.com",98],["isgfrm.com",99],["advertisertape.com",100],["watchadsontape.com",100],["vosfemmes.com",101],["voyeurfrance.net",101],["hyundaitucson.info",102],["exambd.net",103],["cgtips.org",104],["freewebcart.com",105],["freemagazines.top",105],["siamblockchain.com",105],["emuenzen.de",106],["kickass.*",107],["unblocked.id",109],["listendata.com",110],["7xm.xyz",110],["fastupload.io",110],["azmath.info",110],["wouterplanet.com",111],["xenvn.com",112],["4kporn.xxx",113],["androidacy.com",114],["4porn4.com",115],["bestpornflix.com",116],["freeroms.com",116],["andhrafriends.com",116],["723qrh1p.fun",116],["98zero.com",117],["mediaset.es",117],["hwbusters.com",117],["beatsnoop.com",118],["fetchpik.com",118],["hackerranksolution.in",118],["camsrip.com",118],["file.org",118],["btcbunch.com",120],["teachoo.com",[121,122]],["mafiatown.pl",123],["bitcotasks.com",124],["hilites.today",125],["udvl.com",126],["www.chip.de",[127,128,129,130]],["topsporter.net",131],["sportshub.to",131],["myanimelist.net",132],["unofficialtwrp.com",133],["codec.kyiv.ua",133],["kimcilonlyofc.com",133],["bitcosite.com",134],["bitzite.com",134],["teluguflix.*",135],["hacoos.com",136],["watchhentai.net",137],["hes-goals.io",137],["pkbiosfix.com",137],["casi3.xyz",137],["zefoy.com",138],["mailgen.biz",139],["tempinbox.xyz",139],["vidello.net",140],["newscon.org",141],["yunjiema.top",141],["pcgeeks-games.com",141],["resizer.myct.jp",142],["gametohkenranbu.sakuraweb.com",143],["jisakuhibi.jp",144],["rank1-media.com",144],["lifematome.blog",145],["fm.sekkaku.net",146],["dvdrev.com",147],["betweenjpandkr.blog",148],["nft-media.net",149],["ghacks.net",150],["leak.sx",151],["paste.bin.sx",151],["pornleaks.in",151],["khoaiphim.com",153],["haafedk2.com",154],["jovemnerd.com.br",155],["totalcsgo.com",156],["manysex.com",157],["gaminginfos.com",158],["tinxahoivn.com",159],["m.4khd.com",160],["westmanga.*",160],["automoto.it",161],["fordownloader.com",162],["codelivly.com",163],["tchatche.com",164],["cryptoearns.com",164],["lordchannel.com",165],["novelhall.com",166],["bagi.co.in",167],["keran.co",167],["biblestudytools.com",168],["christianheadlines.com",168],["ibelieve.com",168],["kuponigo.com",169],["inxxx.com",170],["bemyhole.com",170],["embedwish.com",171],["jenismac.com",172],["vxetable.cn",173],["luluvid.com",174],["daddylive1.*",174],["esportivos.*",174],["instream.pro",174],["poscitechs.*",174],["powerover.online",174],["sportea.link",174],["ustream.pro",174],["animeshqip.site",174],["apkship.shop",174],["filedot.to",174],["hdstream.one",174],["kingstreamz.site",174],["live.fastsports.store",174],["livesnow.me",174],["livesports4u.pw",174],["nuxhallas.click",174],["papahd.info",174],["rgshows.me",174],["sportmargin.live",174],["sportmargin.online",174],["sportsloverz.xyz",174],["supertipzz.online",174],["ultrastreamlinks.xyz",174],["webmaal.cfd",174],["wizistreamz.xyz",174],["educ4m.com",174],["fromwatch.com",174],["visualnewshub.com",174],["donghuaworld.com",175],["letsdopuzzles.com",176],["rediff.com",177],["igay69.com",178],["dzapk.com",179],["darknessporn.com",180],["familyporner.com",180],["freepublicporn.com",180],["pisshamster.com",180],["punishworld.com",180],["xanimu.com",180],["tainio-mania.online",181],["eroticmoviesonline.me",182],["series9movies.com",182],["teleclub.xyz",183],["ecamrips.com",184],["showcamrips.com",184],["tucinehd.com",185],["uyeshare.cc",185],["9animetv.to",186],["qiwi.gg",187],["jornadaperfecta.com",188],["sousou-no-frieren.com",189],["unite-guide.com",191],["thebullspen.com",192],["receitasdaora.online",193],["hiraethtranslation.com",195],["xfreehd.com",196],["freethesaurus.com",197],["thefreedictionary.com",197],["dexterclearance.com",198],["x86.co.kr",199],["onlyfaucet.com",200],["x-x-x.tube",201],["fdownloader.net",202],["thehackernews.com",203],["mielec.pl",204],["treasl.com",205],["mrbenne.com",206],["sportsonline.si",207],["fiuxy2.co",208],["animeunity.to",209],["tokopedia.com",210],["remixsearch.net",211],["remixsearch.es",211],["onlineweb.tools",211],["sharing.wtf",211],["2024tv.ru",212],["modrinth.com",213],["curseforge.com",213],["xnxxcom.xyz",214],["sportsurge.net",215],["joyousplay.xyz",215],["quest4play.xyz",[215,217]],["moneycontrol.com",216],["cookiewebplay.xyz",217],["ilovetoplay.xyz",217],["streamcaster.live",217],["weblivehdplay.ru",217],["nontongo.win",218],["m9.news",219],["callofwar.com",220],["secondhandsongs.com",221],["nohost.one",222],["send.cm",223],["send.now",223],["3rooodnews.net",224],["xxxbfvideo.net",225],["filmy4wap.co.in",226],["filmy4waps.org",226],["gameshop4u.com",227],["regenzi.site",227],["historicaerials.com",[228,229]],["cinemastervip.com",229],["handirect.fr",230],["fsiblog3.club",231],["kamababa.desi",231],["sat-sharing.com",231],["getfiles.co.uk",232],["genelify.com",233],["dhtpre.com",234],["xbaaz.com",235],["lineupexperts.com",237],["fearmp4.ru",238],["appnee.com",239],["pornoxo.com",240],["m.shuhaige.net",241],["streamingnow.mov",242],["thesciencetoday.com",243],["sportnews.to",243],["ghbrisk.com",245],["iplayerhls.com",245],["bacasitus.com",246],["katoikos.world",246],["abstream.to",247],["pawastreams.pro",248],["rebajagratis.com",249],["tv.latinlucha.es",249],["fetcheveryone.com",250],["reviewdiv.com",251],["laurelberninteriors.com",252],["godlike.com",253],["godlikeproductions.com",253],["bestsportslive.org",254],["alexsports.*>>",255],["btvsports.my>>",255],["cr7-soccer.store>>",255],["e2link.link>>",255],["fsportshd.xyz>>",255],["kakarotfoot.ru>>",255],["pelotalibrevivo.net>>",255],["powerover.site>>",255],["redditsoccerstreams.name>>",255],["sportstohfa.online>>",255],["sportzonline.site>>",255],["streamshunters.eu>>",255],["totalsportek1000.com>>",255],["worldsports.*>>",255],["7fractals.icu",255],["allevertakstream.space",255],["brainknock.net",255],["btvsports.my",255],["capo6play.com",255],["capoplay.net",255],["cdn256.xyz",255],["courseleader.net",255],["cr7-soccer.store",255],["dropbang.net",255],["e2link.link",255],["hornpot.net",255],["fsportshd.xyz",255],["ihdstreams.*",255],["kakarotfoot.ru",255],["meltol.net",255],["nativesurge.net",255],["powerover.site",255],["snapinstadownload.xyz",255],["sportstohfa.online",255],["sportzonline.site",255],["stellarthread.com",255],["streamshunters.eu",255],["totalsportek1000.com",255],["voodc.com",255],["wavewalt.me",255],["worldsports.*",255],["ziggogratis.site",255],["bestreamsports.org",256],["streamhls.to",258],["xmalay1.net",259],["letemsvetemapplem.eu",260],["pc-builds.com",261],["emoji.gg",263],["pfps.gg",264],["live4all.net",265],["pokemon-project.com",266],["umatechnology.org",267],["moviesonlinefree.*",268],["fileszero.com",269],["viralharami.com",269],["wstream.cloud",269],["bmamag.com",270],["bmacanberra.wpcomstaging.com",270],["mmsbee42.com",271],["mmsmasala.com",271],["idlixku.com",272],["andrenalynrushplay.cfd",273],["fnjplay.xyz",273],["porn4fans.com",275],["kaliscan.io",276],["webnoveltranslations.com",277],["techbloat.com",278],["elamigosweb.com",279],["mangacrab.org",280],["webtoon.xyz",281],["manhwaclub.net",282],["edumail.su",283],["rainmail.xyz",283],["mlbbox.me",284],["mgeko.cc",285],["sizecharts.net",286],["talksport.com",288],["cefirates.com",289],["comicleaks.com",289],["tapmyback.com",289],["ping.gg",289],["nookgaming.com",289],["creatordrop.com",289],["bitdomain.biz",289],["fort-shop.kiev.ua",289],["accuretawealth.com",289],["resourceya.com",289],["tracktheta.com",289],["adaptive.marketing",289],["camberlion.com",289],["trybawaryjny.pl",289],["segops.madisonspecs.com",289],["stresshelden-coaching.de",289],["controlconceptsusa.com",289],["ryaktive.com",289],["tip.etip-staging.etip.io",289],["future-fortune.com",290],["furucombo.app",290],["bolighub.dk",290],["intercity.technology",291],["freelancer.taxmachine.be",291],["adria.gg",291],["fjlaboratories.com",291],["abhijith.page",291],["helpmonks.com",291],["dataunlocker.com",292],["proboards.com",293],["winclassic.net",293],["farmersjournal.ie",294],["jxoplay.xyz",296],["zorroplay.xyz",296],["dlhd.*>>",296]]);
const exceptionsMap = new Map([["chatango.com",[9,296]],["twitter.com",[9]],["youtube.com",[9]]]);
const hasEntities = true;
const hasAncestors = true;

const collectArgIndices = (hn, map, out) => {
    let argsIndices = map.get(hn);
    if ( argsIndices === undefined ) { return; }
    if ( typeof argsIndices !== 'number' ) {
        for ( const argsIndex of argsIndices ) {
            out.add(argsIndex);
        }
    } else {
        out.add(argsIndices);
    }
};

const indicesFromHostname = (hostname, suffix = '') => {
    const hnParts = hostname.split('.');
    const hnpartslen = hnParts.length;
    if ( hnpartslen === 0 ) { return; }
    for ( let i = 0; i < hnpartslen; i++ ) {
        const hn = `${hnParts.slice(i).join('.')}${suffix}`;
        collectArgIndices(hn, hostnamesMap, todoIndices);
        collectArgIndices(hn, exceptionsMap, tonotdoIndices);
    }
    if ( hasEntities ) {
        const n = hnpartslen - 1;
        for ( let i = 0; i < n; i++ ) {
            for ( let j = n; j > i; j-- ) {
                const en = `${hnParts.slice(i,j).join('.')}.*${suffix}`;
                collectArgIndices(en, hostnamesMap, todoIndices);
                collectArgIndices(en, exceptionsMap, tonotdoIndices);
            }
        }
    }
};

const entries = (( ) => {
    const docloc = document.location;
    const origins = [ docloc.origin ];
    if ( docloc.ancestorOrigins ) {
        origins.push(...docloc.ancestorOrigins);
    }
    return origins.map((origin, i) => {
        const beg = origin.lastIndexOf('://');
        if ( beg === -1 ) { return; }
        const hn = origin.slice(beg+3)
        const end = hn.indexOf(':');
        return { hn: end === -1 ? hn : hn.slice(0, end), i };
    }).filter(a => a !== undefined);
})();
if ( entries.length === 0 ) { return; }

const todoIndices = new Set();
const tonotdoIndices = new Set();

indicesFromHostname(entries[0].hn);
if ( hasAncestors ) {
    for ( const entry of entries ) {
        if ( entry.i === 0 ) { continue; }
        indicesFromHostname(entry.hn, '>>');
    }
}

// Apply scriplets
for ( const i of todoIndices ) {
    if ( tonotdoIndices.has(i) ) { continue; }
    try { removeNodeText(...argsList[i]); }
    catch { }
}

/******************************************************************************/

// End of local scope
})();

void 0;
