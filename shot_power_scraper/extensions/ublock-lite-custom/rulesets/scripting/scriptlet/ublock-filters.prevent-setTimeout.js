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
(function uBOL_preventSetTimeout() {

/******************************************************************************/

function preventSetTimeout(
    needleRaw = '',
    delayRaw = ''
) {
    const safe = safeSelf();
    const logPrefix = safe.makeLogPrefix('prevent-setTimeout', needleRaw, delayRaw);
    const needleNot = needleRaw.charAt(0) === '!';
    const reNeedle = safe.patternToRegex(needleNot ? needleRaw.slice(1) : needleRaw);
    const range = new RangeParser(delayRaw);
    proxyApplyFn('setTimeout', function(context) {
        const { callArgs } = context;
        const a = callArgs[0] instanceof Function
            ? safe.String(safe.Function_toString(callArgs[0]))
            : safe.String(callArgs[0]);
        const b = callArgs[1];
        if ( needleRaw === '' && range.unbound() ) {
            safe.uboLog(logPrefix, `Called:\n${a}\n${b}`);
            return context.reflect();
        }
        if ( reNeedle.test(a) !== needleNot && range.test(b) ) {
            callArgs[0] = function(){};
            safe.uboLog(logPrefix, `Prevented:\n${a}\n${b}`);
        }
        return context.reflect();
    });
}

function proxyApplyFn(
    target = '',
    handler = ''
) {
    let context = globalThis;
    let prop = target;
    for (;;) {
        const pos = prop.indexOf('.');
        if ( pos === -1 ) { break; }
        context = context[prop.slice(0, pos)];
        if ( context instanceof Object === false ) { return; }
        prop = prop.slice(pos+1);
    }
    const fn = context[prop];
    if ( typeof fn !== 'function' ) { return; }
    if ( proxyApplyFn.CtorContext === undefined ) {
        proxyApplyFn.ctorContexts = [];
        proxyApplyFn.CtorContext = class {
            constructor(...args) {
                this.init(...args);
            }
            init(callFn, callArgs) {
                this.callFn = callFn;
                this.callArgs = callArgs;
                return this;
            }
            reflect() {
                const r = Reflect.construct(this.callFn, this.callArgs);
                this.callFn = this.callArgs = this.private = undefined;
                proxyApplyFn.ctorContexts.push(this);
                return r;
            }
            static factory(...args) {
                return proxyApplyFn.ctorContexts.length !== 0
                    ? proxyApplyFn.ctorContexts.pop().init(...args)
                    : new proxyApplyFn.CtorContext(...args);
            }
        };
        proxyApplyFn.applyContexts = [];
        proxyApplyFn.ApplyContext = class {
            constructor(...args) {
                this.init(...args);
            }
            init(callFn, thisArg, callArgs) {
                this.callFn = callFn;
                this.thisArg = thisArg;
                this.callArgs = callArgs;
                return this;
            }
            reflect() {
                const r = Reflect.apply(this.callFn, this.thisArg, this.callArgs);
                this.callFn = this.thisArg = this.callArgs = this.private = undefined;
                proxyApplyFn.applyContexts.push(this);
                return r;
            }
            static factory(...args) {
                return proxyApplyFn.applyContexts.length !== 0
                    ? proxyApplyFn.applyContexts.pop().init(...args)
                    : new proxyApplyFn.ApplyContext(...args);
            }
        };
        proxyApplyFn.isCtor = new Map();
    }
    if ( proxyApplyFn.isCtor.has(target) === false ) {
        proxyApplyFn.isCtor.set(target, fn.prototype?.constructor === fn);
    }
    const fnStr = fn.toString();
    const toString = (function toString() { return fnStr; }).bind(null);
    const proxyDetails = {
        apply(target, thisArg, args) {
            return handler(proxyApplyFn.ApplyContext.factory(target, thisArg, args));
        },
        get(target, prop) {
            if ( prop === 'toString' ) { return toString; }
            return Reflect.get(target, prop);
        },
    };
    if ( proxyApplyFn.isCtor.get(target) ) {
        proxyDetails.construct = function(target, args) {
            return handler(proxyApplyFn.CtorContext.factory(target, args));
        };
    }
    context[prop] = new Proxy(fn, proxyDetails);
}

class RangeParser {
    constructor(s) {
        this.not = s.charAt(0) === '!';
        if ( this.not ) { s = s.slice(1); }
        if ( s === '' ) { return; }
        const pos = s.indexOf('-');
        if ( pos !== 0 ) {
            this.min = this.max = parseInt(s, 10) || 0;
        }
        if ( pos !== -1 ) {
            this.max = parseInt(s.slice(pos + 1), 10) || Number.MAX_SAFE_INTEGER;
        }
    }
    unbound() {
        return this.min === undefined && this.max === undefined;
    }
    test(v) {
        const n = Math.min(Math.max(Number(v) || 0, 0), Number.MAX_SAFE_INTEGER);
        if ( this.min === this.max ) {
            return (this.min === undefined || n === this.min) !== this.not;
        }
        if ( this.min === undefined ) {
            return (n <= this.max) !== this.not;
        }
        if ( this.max === undefined ) {
            return (n >= this.min) !== this.not;
        }
        return (n >= this.min && n <= this.max) !== this.not;
    }
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
const argsList = [["]();}","500"],[")](this,...","3000-6000"],["(new Error(","3000-6000"],[".offsetHeight>0"],["adblock"],["/offsetHeight|loaded/"],["googleFC"],["adb"],["adBlockerDetected"],["show"],["InfMediafireMobileFunc","1000"],["admc"],["apstagLOADED"],["/Adb|moneyDetect/"],["disableDeveloper"],["Blocco","2000"],["test","0"],["checkAdblockUser","1000"],["checkPub","6000"],["'0x"],["document.querySelector","5000"],["nextFunction","250"],["backRedirect"],["document.querySelectorAll","1000"],["style"],["clientHeight"],["addEventListener","0"],["nextFunction","2000"],["byepopup","5000"],["additional_src","300"],["()","2000"],["css_class.show"],["CANG","3000"],["updato-overlay","500"],["innerText","2000"],["alert","8000"],["css_class"],["()","50"],["debugger"],["initializeCourier","3000"],["redirectPage"],["_0x","2000"],["ads","750"],["location.href","500"],["Adblock","5000"],["disable","200"],["CekAab","0"],["rbm_block_active","1000"],["show()"],["_0x"],["n.trigger","1"],["abDetected"],["$"],["KeepOpeningPops","1000"],["location.href"],["adb","0"],["adBlocked"],["warning","100"],["adsbygoogle"],["adblock_popup","500"],["Adblock"],["location.href","10000"],["keep-ads","2000"],["#rbm_block_active","1000"],["google_jobrunner"],["null","4000"],["()","2500"],["myaabpfun","3000"],["adFilled","2500"],["()","15000"],["showPopup"],["adrecover"],["()","1000"],["document.cookie","2500"],["window.open"],["innerHTML"],["readyplayer","2000"],["/innerHTML|AdBlock/"],["checkStopBlock"],["adspot_top","1500"],["/offsetHeight|google|Global/"],["an_message","500"],["Adblocker","10000"],["timeoutChecker"],["bait","1"],["ai_adb"],["displayCookieWallBanner"],["pum-open"],["overlay","2000"],["/adblock/i"],["Math.round","1000"],["adblock","5"],["ag_adBlockerDetected"],["null"],["adb","6000"],["sadbl"],["brave_load_popup"],["adsbytrafficjunkycontext"],["ipod"],["offsetWidth"],["/$|adBlock/"],["()"],["AdBlock"],["stop-scrolling"],["Adv"],["blockUI","2000"],["mdpDeBlocker"],["/_0x|debug/"],["/ai_adb|_0x/"],["adBlock"],["","1"],["undefined"],["check","1"],["adsBlocked"],["nextFunction"],["blocker"],["afs_ads","2000"],["bait"],["getComputedStyle","250"],["blocked"],["{r()","0"],["nextFunction","450"],["Debug"],["r()","0"],["test","100"],["purple_box"],["checkSiteNormalLoad"],["0x"],["adBlockOverlay"],["Detected","500"],["mdp"],["modal"],[".show","1000"],["afterOpen"],[".show"],["showModal"],["blur"],["samOverlay"],["native"],["bADBlock"],["location"],["alert"],["t()","0"],["ads"],["alert","2000"],["/adblock|isRequestPresent/"],["documentElement.innerHTML"],["_0x","500"],["isRequestPresent"],["checkAdblock"],["1e3*"],["","2000"],["/^/","1000"],["checkAdBlock"],["displayAdBlockerMessage"],["push","500"],[".call(null)","10"],[".call(null)"],["(null)","10"],["userHasAdblocker"],["/loadMomoVip|loadExo|includeSpecial/"],["appendChild"],["affiliate"],["getComputedStyle"],["displayMessage","2000"],["AdDetect"],["ai_"],["error-report.com"],["loader.min.js"],["content-loader.com"],["()=>","5000"],["[native code]","500"],["consent"],["await _0x"],["adbl"],["openPopunder"],["closeBanner"],[".getComputedStyle"],["offsetHeight"],["offsetLeft"],["height"],["charAt"],["checkAds"],["fadeIn","0"],["jQuery"],["/^/"],["check"],["eabdModal"],["ab_root.show"],["gaData"],["ad"],["prompt","1000"],["googlefc"],["adblock detection"],[".offsetHeight","100"],["popState"],["ad-block-popup"],["exitTimer"],["innerHTML.replace"],["eabpDialog"],["adsense"],["/Adblock|_ad_/"],["googletag"],["f.parentNode.removeChild(f)","100"],["swal","500"],["keepChecking","1000"],["openPopup"],[".offsetHeight"],["()=>{"],["nitroAds"],["class.scroll","1000"],["disableDeveloperTools"],["Check"],["insertBefore"],["css_class.scroll"],["/null|Error/","10000"],["/out.php"],["/0x|devtools/"],["location.replace","300"],["window.location.href"],["fetch"],["window.location.href=link"],["reachGoal"],["Adb"],["ai"],["","3000"],["/width|innerHTML/"],["magnificPopup"],["/debugger|offsetParent/"],["adblockEnabled"],["google_ad"],["document.location"],["google"],["answers"],["top-right","2000"],["enforceAdStatus"],["display","5000"],["eb"],["/adb/i"],[").show()"],["","1000"],["site-access"],["/Ads|adbl|offsetHeight/"],["/show|innerHTML/"],["/show|document\\.createElement/"],["MobileInGameGames"],["Msg"],["UABP"],["()","150"],["href"],["aaaaa-modal"],["()=>"],["null","10"],["","500"],["pop"],["/adbl/i"],["-0x"],["display"],["gclid"],["event","3000"],["rejectWith"],[".data?"],["refresh"],["location.href","3000"],["ga"],["keepChecking"],["myTestAd"],["click"],["Ads"],["ShowAdBLockerNotice"],["ad_listener"],["open"],["(!0)"],["Delay"],["/appendChild|e\\(\"/"],["=>"],["site-access-popup"],["data?"],["checkAdblockUser"],["offsetHeight","100"],["/salesPopup|mira-snackbar/"],["detectImgLoad"],["offsetHeight","200"],["detector"],["replace"],["touchstart"],["siteAccessFlag"],["ab"],["/adblocker|alert/"],["redURL"],["/children\\('ins'\\)|Adblock|adsbygoogle/"],["displayMessage"],["chkADB"],["onDetected"],["fuckadb"],["detect"],["siteAccessPopup"],["/adsbygoogle|adblock|innerHTML|setTimeout/"],["akadb"],["biteDisplay"],["/[a-z]\\(!0\\)/","800"],["ad_block"],["/detectAdBlocker|window.open/"],["adBlockDetected"],["popUnder"],["/GoToURL|delay/"],["window.location.href","300"],[".redirect"],["/AdBlock/i"],["popup"],["/adScriptPath|MMDConfig/"],["/native|\\{n\\(\\)/"],["psresimler"],["adblocker"],["EzoIvent"],["/Detect|adblock|style\\.display|\\[native code]|\\.call\\(null\\)/"],["removeChild"],["offset"],["","2000-5000"],["contrformpub"],["trigger","0"],["ADB"],["/\\.append|\\.innerHTML|undefined|\\.css|blocker|flex|\\$\\('|obfuscatedMsg/"],["warn"],["getComputedStyle","2000"],["video-popup"],["detectAdblock"],["detectAdBlocker"],["nads"],["current.children"],["adStatus"],["BN_CAMPAIGNS"],["media_place_list"],["...","300"],["/\\{[a-z]\\(!0\\)\\}/"],["stackTrace"],["inner-ad"],["_ET"],[".clientHeight"],["getComputedStyle(el)"],["location.replace"],["console.clear"],["ad_block_detector"],["document.createElement"],["getComputedStyle(testAd)"],[".adv-"],["/Executed|modal/"],["document['\\x"],["hasAdblock"],["/adblock|isblock/i"],["visibility","2000"],["/location\\.(replace|href)|stopAndExitFullscreen/"],["displayAdBlockedVideo"],["test.remove","100"],["adblock","2000"],["adBlockerModal"],["","10000-15000"],["/adex|loadAds|adCollapsedCount|ad-?block/i"],["length"],["atob","120000"],["#ad_blocker_detector"],["push"],["AdBlocker"],["wbDeadHinweis"],["","10000"],["fired"],["mode:\"no-cors\""],["Visibility"],["ast"],["googlesyndication"],["start"],["moneyDetect"],["sub"],["/createElement|addEventListener|clientHeight/"],["testAd"],[".redirected"],["TNCMS.DMP"],["[native code]","120000"]];
const hostnamesMap = new Map([["poophq.com",0],["veev.to",0],["dogdrip.net",1],["infinityfree.com",1],["smsonline.cloud",[1,2]],["faqwiki.us",3],["mail.yahoo.com",[4,321]],["maxcheaters.com",4],["postimees.ee",4],["police.community",4],["gisarea.com",4],["schaken-mods.com",4],["tvnet.lv",4],["theclashify.com",4],["txori.com",4],["olarila.com",4],["deletedspeedstreams.blogspot.com",4],["schooltravelorganiser.com",4],["xhardhempus.net",4],["mhn.quest",4],["leagueofgraphs.com",4],["hieunguyenphoto.com",4],["benzinpreis.de",4],["tvtropes.org",5],["lastampa.it",6],["m.timesofindia.com",7],["timesofindia.indiatimes.com",7],["youmath.it",7],["redensarten-index.de",7],["lesoir.be",7],["electriciansforums.net",7],["keralatelecom.info",7],["universegunz.net",7],["happypenguin.altervista.org",7],["everyeye.it",7],["eztv.*",7],["bluedrake42.com",7],["supermarioemulator.com",7],["futbollibrehd.com",7],["eska.pl",7],["eskarock.pl",7],["voxfm.pl",7],["mathaeser.de",7],["betaseries.com",7],["free-sms-receive.com",7],["sms-receive-online.com",7],["computer76.ru",7],["golem.de",[8,9,156]],["hdbox.ws",9],["todopolicia.com",9],["scat.gold",9],["freecoursesite.com",9],["windowcleaningforums.co.uk",9],["cruisingearth.com",9],["hobby-machinist.com",9],["freegogpcgames.com",9],["latitude.to",9],["kitchennovel.com",9],["w3layouts.com",9],["blog.receivefreesms.co.uk",9],["eductin.com",9],["dealsfinders.blog",9],["audiobooks4soul.com",9],["downloadr.in",9],["topcomicporno.com",9],["sushi-scan.*",9],["celtadigital.com",9],["iptvrun.com",9],["adsup.lk",9],["cryptomonitor.in",9],["areatopik.com",9],["cardscanner.co",9],["nullforums.net",9],["courseclub.me",9],["tamarindoyam.com",9],["jeep-cj.com",9],["choiceofmods.com",9],["myqqjd.com",9],["ssdtop.com",9],["apkhex.com",9],["gezegenforum.com",9],["iptvapps.net",9],["null-scripts.net",9],["nullscripts.net",9],["bloground.ro",9],["witcherhour.com",9],["ottverse.com",9],["torrentmac.net",9],["mazakony.com",9],["laptechinfo.com",9],["mc-at.org",9],["playstationhaber.com",9],["seriesperu.com",9],["spigotunlocked.*",9],["pesprofessionals.com",9],["wpsimplehacks.com",9],["sportshub.to",[9,265]],["topsporter.net",[9,265]],["darkwanderer.net",9],["truckingboards.com",9],["coldfrm.org",9],["azrom.net",9],["freepatternsarea.com",9],["alttyab.net",9],["ahmedmode.*",9],["esopress.com",9],["nesiaku.my.id",9],["jipinsoft.com",9],["truthnews.de",9],["farsinama.com",9],["worldofiptv.com",9],["vuinsider.com",9],["crazydl.net",9],["gamemodsbase.com",9],["babiato.tech",9],["secuhex.com",9],["turkishaudiocenter.com",9],["galaxyos.net",9],["bizdustry.com",9],["storefront.com.ng",9],["pkbiosfix.com",9],["casi3.xyz",9],["forum-xiaomi.com",9],["mediafire.com",10],["yts.*",11],["720pstream.*",11],["1stream.*",11],["seattletimes.com",12],["bestgames.com",13],["yiv.com",13],["globalrph.com",14],["e-glossa.it",15],["webcheats.com.br",16],["urlcero.*",17],["gala.fr",18],["gentside.com",18],["geo.fr",18],["hbrfrance.fr",18],["nationalgeographic.fr",18],["ohmymag.com",18],["serengo.net",18],["vsd.fr",18],["short.pe",19],["thefmovies.*",19],["footystreams.net",19],["katestube.com",19],["updato.com",[20,33]],["totaldebrid.*",21],["sandrives.*",21],["daizurin.com",21],["pendekarsubs.us",21],["dreamfancy.org",21],["rysafe.blogspot.com",21],["techacode.com",21],["toppng.com",21],["th-world.com",21],["avjamack.com",21],["avjamak.net",21],["cnnamador.com",22],["nudecelebforum.com",23],["pronpic.org",24],["thewebflash.com",25],["discordfastfood.com",25],["xup.in",25],["popularmechanics.com",26],["comunidadgzone.es",27],["fxporn69.*",27],["mp3fy.com",27],["lebensmittelpraxis.de",27],["aliancapes.*",27],["forum-pokemon-go.fr",27],["praxis-jugendarbeit.de",27],["dictionnaire-medical.net",27],["cle0desktop.blogspot.com",27],["up-load.io",27],["keysbrasil.blogspot.com",27],["hotpress.info",27],["turkleech.com",27],["anibatch.me",27],["anime-i.com",27],["gewinde-normen.de",27],["tucinehd.com",27],["kdramasmaza.com.pk",27],["jellynote.com",28],["eporner.com",29],["pornbimbo.com",30],["4j.com",30],["avoiderrors.com",31],["sitarchive.com",31],["livenewsof.com",31],["topnewsshow.com",31],["gatcha.org",31],["kusonime.com",31],["suicidepics.com",31],["codesnail.com",31],["codingshiksha.com",31],["graphicux.com",31],["citychilli.com",31],["talkjarvis.com",31],["hdmotori.it",32],["tubsexer.*",34],["femdomtb.com",34],["porno-tour.*",34],["lenkino.*",34],["bobs-tube.com",34],["pornfd.com",34],["pornomoll.*",34],["camsclips.*",34],["popno-tour.net",34],["watchmdh.to",34],["camwhores.tv",34],["camhub.cc",34],["elfqrin.com",35],["satcesc.com",36],["apfelpatient.de",36],["lusthero.com",37],["m4ufree.*",38],["m2list.com",38],["embed.nana2play.com",38],["dallasnews.com",39],["lnk.news",40],["lnk.parts",40],["efukt.com",41],["wendycode.com",41],["springfieldspringfield.co.uk",42],["porndoe.com",43],["smsget.net",[44,45]],["kjanime.net",46],["gioialive.it",47],["classicreload.com",48],["scriptzhub.com",48],["hotpornfile.org",49],["coolsoft.altervista.org",49],["hackedonlinegames.com",49],["dailytech-news.eu",49],["settlersonlinemaps.com",49],["ad-doge.com",49],["magdownload.org",49],["kpkuang.org",49],["crypto4yu.com",49],["writedroid.*",49],["thenightwithoutthedawn.blogspot.com",49],["claimlite.club",49],["newscon.org",49],["rl6mans.com",49],["chicoer.com",50],["bostonherald.com",50],["dailycamera.com",50],["sportsplays.com",51],["ebookdz.com",52],["telerium.*",53],["pornvideotop.com",54],["arolinks.com",54],["xstory-fr.com",54],["1337x.*",54],["x1337x.*",54],["1337x.ninjaproxy1.com",54],["ytapi.cc",54],["letribunaldunet.fr",55],["vladan.fr",55],["live-tv-channels.org",56],["eslfast.com",57],["ge-map-overlays.appspot.com",58],["mad4wheels.com",58],["1xanimes.in",58],["logi.im",58],["emailnator.com",58],["claudelog.com",58],["freegamescasual.com",59],["tcpvpn.com",60],["oko.sh",60],["timesnownews.com",60],["timesnowhindi.com",60],["timesnowmarathi.com",60],["zoomtventertainment.com",60],["tsubasa.im",61],["sholah.net",62],["2rdroid.com",62],["bisceglielive.it",63],["openspeedtest.com",64],["addtobucketlist.com",64],["3dzip.org",[64,65]],["ilmeteo.it",64],["wcoforever.com",64],["comprovendolibri.it",64],["healthelia.com",64],["wcoanimedub.tv",64],["wcoforever.net",64],["pandajogosgratis.com.br",66],["5278.cc",67],["pandafreegames.*",68],["tonspion.de",69],["duplichecker.com",70],["plagiarismchecker.co",70],["plagiarismdetector.net",70],["searchenginereports.net",70],["smallseotools.com",71],["linkspaid.com",72],["proxydocker.com",72],["beeimg.com",[73,74]],["emturbovid.com",74],["findjav.com",74],["javggvideo.xyz",74],["mmtv01.xyz",74],["stbturbo.xyz",74],["trailerhg.xyz",74],["turboplayers.xyz",74],["turbovidhls.com",74],["viralharami.com",74],["ftlauderdalebeachcam.com",75],["ftlauderdalewebcam.com",75],["juneauharborwebcam.com",75],["keywestharborwebcam.com",75],["kittycatcam.com",75],["mahobeachcam.com",75],["miamiairportcam.com",75],["morganhillwebcam.com",75],["njwildlifecam.com",75],["nyharborwebcam.com",75],["paradiseislandcam.com",75],["pompanobeachcam.com",75],["portbermudawebcam.com",75],["portcanaveralwebcam.com",75],["portevergladeswebcam.com",75],["portmiamiwebcam.com",75],["portnywebcam.com",75],["portnassauwebcam.com",75],["portstmaartenwebcam.com",75],["portstthomaswebcam.com",75],["porttampawebcam.com",75],["sxmislandcam.com",75],["themes-dl.com",75],["badassdownloader.com",75],["badasshardcore.com",75],["badassoftcore.com",75],["nulljungle.com",75],["teevee.asia",75],["otakukan.com",75],["thoptv.*",76],["gearingcommander.com",77],["generate.plus",78],["calculate.plus",78],["avcesar.com",79],["audiotag.info",80],["tudigitale.it",81],["ibcomputing.com",82],["legia.net",83],["acapellas4u.co.uk",84],["robloxscripts.com",85],["libreriamo.it",85],["postazap.com",85],["filmyzones.com",85],["medebooks.xyz",85],["mashtips.com",85],["marriedgames.com.br",85],["4allprograms.me",85],["shortzzy.*",85],["nurgsm.com",85],["plugincrack.com",85],["gamingdeputy.com",85],["freewebcart.com",85],["gamekult.com",86],["streamhentaimovies.com",87],["konten.co.id",88],["diariodenavarra.es",89],["scripai.com",89],["myfxbook.com",89],["whatfontis.com",89],["katfile.*",89],["tubereader.me",89],["optifine.net",90],["luzernerzeitung.ch",91],["tagblatt.ch",91],["ableitungsrechner.net",92],["alternet.org",93],["gourmetsupremacy.com",93],["shrib.com",94],["streameast.*",95],["thestreameast.*",95],["techclips.net",95],["daddylivehd.*",95],["footyhunter.lol",95],["wecast.to",95],["freecourseweb.com",96],["coursewikia.com",96],["courseboat.com",96],["pornhub.*",97],["lne.es",[98,372]],["pornult.com",99],["webcamsdolls.com",99],["bitcotasks.com",[99,141]],["adsy.pw",99],["playstore.pw",99],["exactpay.online",99],["thothd.to",99],["proplanta.de",100],["textograto.com",101],["voyageforum.com",102],["hmc-id.blogspot.com",102],["myabandonware.com",102],["wcofun.*",102],["ilforumdeibrutti.is",102],["prad.de",[103,156]],["chatta.it",104],["ketubanjiwa.com",105],["nsfw247.to",106],["funzen.net",106],["extremereportbot.com",107],["getintopc.com",108],["qoshe.com",109],["lowellsun.com",110],["mamadu.pl",110],["dobrapogoda24.pl",110],["motohigh.pl",110],["namasce.pl",110],["ultimate-catch.eu",111],["cpopchanelofficial.com",112],["creditcardgenerator.com",113],["creditcardrush.com",113],["bostoncommons.net",113],["thejobsmovie.com",113],["hl-live.de",114],["satoshi-win.xyz",114],["encurtandourl.com",[114,118]],["www-daftarharga.blogspot.com",114],["ear-phone-review.com",114],["telefullenvivo.com",114],["listatv.pl",114],["coin-profits.xyz",114],["relampagomovies.com",114],["wohnmobilforum.de",114],["nulledbear.com",114],["sinnerclownceviri.net",114],["nilopolisonline.com.br",115],["mesquitaonline.com",115],["yellowbridge.com",115],["yaoiotaku.com",116],["moneyhouse.ch",117],["ihow.info",118],["filesus.com",118],["gotxx.*",118],["sturls.com",118],["turbo1.co",118],["hartico.tv",118],["cupra.forum",118],["turkanime.*",119],["valeronevijao.com",119],["yodelswartlike.com",119],["generatesnitrosate.com",119],["gamoneinterrupted.com",119],["metagnathtuggers.com",119],["rationalityaloelike.com",119],["sizyreelingly.com",119],["urochsunloath.com",119],["monorhinouscassaba.com",119],["antecoxalbobbing1010.com",119],["boonlessbestselling244.com",119],["cyamidpulverulence530.com",119],["guidon40hyporadius9.com",119],["449unceremoniousnasoseptal.com",119],["30sensualizeexpression.com",119],["greaseball6eventual20.com",119],["toxitabellaeatrebates306.com",119],["20demidistance9elongations.com",119],["audaciousdefaulthouse.com",119],["fittingcentermondaysunday.com",119],["launchreliantcleaverriver.com",119],["matriculant401merited.com",119],["realfinanceblogcenter.com",119],["telyn610zoanthropy.com",119],["un-block-voe.net",119],["v-o-e-unblock.com",119],["voe-un-block.com",119],["voe-unblock.*",119],["voeunbl0ck.com",119],["voeunblck.com",119],["voeunblk.com",119],["voeunblock.com",119],["voeunblock2.com",119],["voeunblock3.com",119],["agefi.fr",120],["cariskuy.com",121],["letras2.com",121],["yusepjaelani.blogspot.com",122],["letras.mus.br",123],["eletronicabr.com",124],["mtlurb.com",125],["onemanhua.com",126],["laksa19.github.io",127],["javcl.com",127],["tvlogy.to",127],["rp5.*",127],["live.dragaoconnect.net",127],["seznamzpravy.cz",127],["xerifetech.com",127],["freemcserver.net",127],["t3n.de",128],["allindiaroundup.com",129],["tapchipi.com",130],["dcleakers.com",130],["esgeeks.com",130],["pugliain.net",130],["uplod.net",130],["worldfreeware.com",130],["tech-blogs.com",130],["cardiagn.com",130],["fikiri.net",130],["myhackingworld.com",130],["vectorizer.io",131],["onehack.us",131],["smgplaza.com",131],["thapcam.net",131],["breznikar.com",131],["thefastlaneforum.com",132],["5flix.top",133],["bembed.net",133],["embedv.net",133],["javguard.club",133],["listeamed.net",133],["v6embed.xyz",133],["vembed.*",133],["vid-guard.com",133],["vidguardto.xyz",133],["yesmovies.*>>",133],["pistona.xyz",133],["vinomo.xyz",133],["moflix-stream.*",[133,162]],["trade2win.com",134],["modagamers.com",135],["khatrimaza.*",135],["freemagazines.top",135],["pogolinks.*",135],["straatosphere.com",135],["nullpk.com",135],["adslink.pw",135],["downloadudemy.com",135],["picgiraffe.com",135],["weadown.com",135],["freepornsex.net",135],["nurparatodos.com.ar",135],["popcornstream.*",136],["routech.ro",136],["hokej.net",136],["turkmmo.com",137],["acdriftingpro.com",138],["palermotoday.it",139],["baritoday.it",139],["trentotoday.it",139],["agrigentonotizie.it",139],["anconatoday.it",139],["arezzonotizie.it",139],["avellinotoday.it",139],["bresciatoday.it",139],["brindisireport.it",139],["casertanews.it",139],["cataniatoday.it",139],["cesenatoday.it",139],["chietitoday.it",139],["forlitoday.it",139],["frosinonetoday.it",139],["genovatoday.it",139],["ilpescara.it",139],["ilpiacenza.it",139],["latinatoday.it",139],["lecceprima.it",139],["leccotoday.it",139],["livornotoday.it",139],["messinatoday.it",139],["milanotoday.it",139],["modenatoday.it",139],["monzatoday.it",139],["novaratoday.it",139],["padovaoggi.it",139],["parmatoday.it",139],["perugiatoday.it",139],["pisatoday.it",139],["quicomo.it",139],["ravennatoday.it",139],["reggiotoday.it",139],["riminitoday.it",139],["romatoday.it",139],["salernotoday.it",139],["sondriotoday.it",139],["sportpiacenza.it",139],["ternitoday.it",139],["today.it",139],["torinotoday.it",139],["trevisotoday.it",139],["triesteprima.it",139],["udinetoday.it",139],["veneziatoday.it",139],["vicenzatoday.it",139],["thumpertalk.com",140],["austiblox.net",140],["thelayoff.com",141],["shorterall.com",141],["maxstream.video",141],["tvepg.eu",141],["manwan.xyz",141],["dailymaverick.co.za",142],["ludigames.com",143],["made-by.org",143],["worldtravelling.com",143],["technichero.com",143],["androidadult.com",143],["aeroxplorer.com",143],["sportitalialive.com",143],["adrinolinks.com",144],["link.vipurl.in",144],["nanolinks.in",144],["fadedfeet.com",145],["homeculina.com",145],["ineedskin.com",145],["kenzo-flowertag.com",145],["lawyex.co",145],["mdn.lol",145],["starkroboticsfrc.com",146],["sinonimos.de",146],["antonimos.de",146],["quesignifi.ca",146],["tiktokrealtime.com",146],["tiktokcounter.net",146],["tpayr.xyz",146],["poqzn.xyz",146],["ashrfd.xyz",146],["rezsx.xyz",146],["tryzt.xyz",146],["ashrff.xyz",146],["rezst.xyz",146],["dawenet.com",146],["erzar.xyz",146],["waezm.xyz",146],["waezg.xyz",146],["blackwoodacademy.org",146],["cryptednews.space",146],["vivuq.com",146],["swgop.com",146],["vbnmll.com",146],["telcoinfo.online",146],["dshytb.com",146],["bitzite.com",147],["coingraph.us",148],["impact24.us",148],["tpi.li",149],["oii.la",149],["www.apkmoddone.com",150],["sitemini.io.vn",151],["vip1s.top",151],["dl.apkmoddone.com",152],["phongroblox.com",152],["financacerta.com",153],["encurtads.net",153],["shortencash.click",154],["lablue.*",155],["4-liga.com",156],["4fansites.de",156],["4players.de",156],["9monate.de",156],["aachener-nachrichten.de",156],["aachener-zeitung.de",156],["abendblatt.de",156],["abendzeitung-muenchen.de",156],["about-drinks.com",156],["abseits-ka.de",156],["airliners.de",156],["ajaxshowtime.com",156],["allgemeine-zeitung.de",156],["alpin.de",156],["antenne.de",156],["arcor.de",156],["areadvd.de",156],["areamobile.de",156],["ariva.de",156],["astronews.com",156],["aussenwirtschaftslupe.de",156],["auszeit.bio",156],["auto-motor-und-sport.de",156],["auto-service.de",156],["autobild.de",156],["autoextrem.de",156],["autopixx.de",156],["autorevue.at",156],["autotrader.nl",156],["az-online.de",156],["baby-vornamen.de",156],["babyclub.de",156],["bafoeg-aktuell.de",156],["berliner-kurier.de",156],["berliner-zeitung.de",156],["bigfm.de",156],["bikerszene.de",156],["bildderfrau.de",156],["blackd.de",156],["blick.de",156],["boerse-online.de",156],["boerse.de",156],["boersennews.de",156],["braunschweiger-zeitung.de",156],["brieffreunde.de",156],["brigitte.de",156],["buerstaedter-zeitung.de",156],["buffed.de",156],["businessinsider.de",156],["buzzfeed.at",156],["buzzfeed.de",156],["caravaning.de",156],["cavallo.de",156],["chefkoch.de",156],["cinema.de",156],["clever-tanken.de",156],["computerbild.de",156],["computerhilfen.de",156],["comunio-cl.com",156],["comunio.*",156],["connect.de",156],["chip.de",156],["da-imnetz.de",156],["dasgelbeblatt.de",156],["dbna.com",156],["dbna.de",156],["deichstube.de",156],["deine-tierwelt.de",156],["der-betze-brennt.de",156],["derwesten.de",156],["desired.de",156],["dhd24.com",156],["dieblaue24.com",156],["digitalfernsehen.de",156],["dnn.de",156],["donnerwetter.de",156],["e-hausaufgaben.de",156],["e-mountainbike.com",156],["eatsmarter.de",156],["echo-online.de",156],["ecomento.de",156],["einfachschoen.me",156],["elektrobike-online.com",156],["eltern.de",156],["epochtimes.de",156],["essen-und-trinken.de",156],["express.de",156],["extratipp.com",156],["familie.de",156],["fanfiktion.de",156],["fehmarn24.de",156],["fettspielen.de",156],["fid-gesundheitswissen.de",156],["finanzen.*",156],["finanznachrichten.de",156],["finanztreff.de",156],["finya.de",156],["firmenwissen.de",156],["fitforfun.de",156],["fnp.de",156],["football365.fr",156],["formel1.de",156],["fr.de",156],["frankfurter-wochenblatt.de",156],["freenet.de",156],["fremdwort.de",156],["froheweihnachten.info",156],["frustfrei-lernen.de",156],["fuldaerzeitung.de",156],["funandnews.de",156],["fussballdaten.de",156],["futurezone.de",156],["gala.de",156],["gamepro.de",156],["gamersglobal.de",156],["gamesaktuell.de",156],["gamestar.de",156],["gameswelt.*",156],["gamezone.de",156],["gartendialog.de",156],["gartenlexikon.de",156],["gedichte.ws",156],["geissblog.koeln",156],["gelnhaeuser-tageblatt.de",156],["general-anzeiger-bonn.de",156],["geniale-tricks.com",156],["genialetricks.de",156],["gesund-vital.de",156],["gesundheit.de",156],["gevestor.de",156],["gewinnspiele.tv",156],["giessener-allgemeine.de",156],["giessener-anzeiger.de",156],["gifhorner-rundschau.de",156],["giga.de",156],["gipfelbuch.ch",156],["gmuender-tagespost.de",156],["gruenderlexikon.de",156],["gusto.at",156],["gut-erklaert.de",156],["gutfuerdich.co",156],["hallo-muenchen.de",156],["hamburg.de",156],["hanauer.de",156],["hardwareluxx.de",156],["hartziv.org",156],["harzkurier.de",156],["haus-garten-test.de",156],["hausgarten.net",156],["haustec.de",156],["haz.de",156],["heftig.*",156],["heidelberg24.de",156],["heilpraxisnet.de",156],["heise.de",156],["helmstedter-nachrichten.de",156],["hersfelder-zeitung.de",156],["hftg.co",156],["hifi-forum.de",156],["hna.de",156],["hochheimer-zeitung.de",156],["hoerzu.de",156],["hofheimer-zeitung.de",156],["iban-rechner.de",156],["ikz-online.de",156],["immobilienscout24.de",156],["ingame.de",156],["inside-digital.de",156],["inside-handy.de",156],["investor-verlag.de",156],["jappy.com",156],["jpgames.de",156],["kabeleins.de",156],["kachelmannwetter.com",156],["kamelle.de",156],["kicker.de",156],["kindergeld.org",156],["klettern-magazin.de",156],["klettern.de",156],["kochbar.de",156],["kreis-anzeiger.de",156],["kreisbote.de",156],["kreiszeitung.de",156],["ksta.de",156],["kurierverlag.de",156],["lachainemeteo.com",156],["lampertheimer-zeitung.de",156],["landwirt.com",156],["laut.de",156],["lauterbacher-anzeiger.de",156],["leckerschmecker.me",156],["leinetal24.de",156],["lesfoodies.com",156],["levif.be",156],["lifeline.de",156],["liga3-online.de",156],["likemag.com",156],["linux-community.de",156],["linux-magazin.de",156],["live.vodafone.de",156],["ln-online.de",156],["lokalo24.de",156],["lustaufsleben.at",156],["lustich.de",156],["lvz.de",156],["lz.de",156],["mactechnews.de",156],["macwelt.de",156],["macworld.co.uk",156],["mail.de",156],["main-spitze.de",156],["manager-magazin.de",156],["manga-tube.me",156],["mathebibel.de",156],["mathepower.com",156],["maz-online.de",156],["medisite.fr",156],["mehr-tanken.de",156],["mein-kummerkasten.de",156],["mein-mmo.de",156],["mein-wahres-ich.de",156],["meine-anzeigenzeitung.de",156],["meinestadt.de",156],["menshealth.de",156],["mercato365.com",156],["merkur.de",156],["messen.de",156],["metal-hammer.de",156],["metalflirt.de",156],["meteologix.com",156],["minecraft-serverlist.net",156],["mittelbayerische.de",156],["modhoster.de",156],["moin.de",156],["mopo.de",156],["morgenpost.de",156],["motor-talk.de",156],["motorbasar.de",156],["motorradonline.de",156],["motorsport-total.com",156],["motortests.de",156],["mountainbike-magazin.de",156],["moviejones.de",156],["moviepilot.de",156],["mt.de",156],["mtb-news.de",156],["musiker-board.de",156],["musikexpress.de",156],["musikradar.de",156],["mz-web.de",156],["n-tv.de",156],["naumburger-tageblatt.de",156],["netzwelt.de",156],["neuepresse.de",156],["neueroeffnung.info",156],["news.at",156],["news.de",156],["news38.de",156],["newsbreak24.de",156],["nickles.de",156],["nicknight.de",156],["nl.hardware.info",156],["nn.de",156],["nnn.de",156],["nordbayern.de",156],["notebookchat.com",156],["notebookcheck-ru.com",156],["notebookcheck-tr.com",156],["notebookcheck.*",156],["noz-cdn.de",156],["noz.de",156],["nrz.de",156],["nw.de",156],["nwzonline.de",156],["oberhessische-zeitung.de",156],["och.to",156],["oeffentlicher-dienst.info",156],["onlinekosten.de",156],["onvista.de",156],["op-marburg.de",156],["op-online.de",156],["outdoor-magazin.com",156],["outdoorchannel.de",156],["paradisi.de",156],["pc-magazin.de",156],["pcgames.de",156],["pcgameshardware.de",156],["pcwelt.de",156],["pcworld.es",156],["peiner-nachrichten.de",156],["pferde.de",156],["pietsmiet.de",156],["pixelio.de",156],["pkw-forum.de",156],["playboy.de",156],["playfront.de",156],["pnn.de",156],["pons.com",156],["prignitzer.de",156],["profil.at",156],["promipool.de",156],["promobil.de",156],["prosiebenmaxx.de",156],["psychic.de",[156,178]],["quoka.de",156],["radio.at",156],["radio.de",156],["radio.dk",156],["radio.es",156],["radio.fr",156],["radio.it",156],["radio.net",156],["radio.pl",156],["radio.pt",156],["radio.se",156],["ran.de",156],["readmore.de",156],["rechtslupe.de",156],["recording.de",156],["rennrad-news.de",156],["reuters.com",156],["reviersport.de",156],["rhein-main-presse.de",156],["rheinische-anzeigenblaetter.de",156],["rimondo.com",156],["roadbike.de",156],["roemische-zahlen.net",156],["rollingstone.de",156],["rot-blau.com",156],["rp-online.de",156],["rtl.de",[156,252]],["rtv.de",156],["rugby365.fr",156],["ruhr24.de",156],["rundschau-online.de",156],["runnersworld.de",156],["safelist.eu",156],["salzgitter-zeitung.de",156],["sat1.de",156],["sat1gold.de",156],["schoener-wohnen.de",156],["schwaebische-post.de",156],["schwarzwaelder-bote.de",156],["serienjunkies.de",156],["shz.de",156],["sixx.de",156],["skodacommunity.de",156],["smart-wohnen.net",156],["sn.at",156],["sozialversicherung-kompetent.de",156],["spiegel.de",156],["spielen.de",156],["spieletipps.de",156],["spielfilm.de",156],["sport.de",156],["sport1.de",156],["sport365.fr",156],["sportal.de",156],["spox.com",156],["stern.de",156],["stuttgarter-nachrichten.de",156],["stuttgarter-zeitung.de",156],["sueddeutsche.de",156],["svz.de",156],["szene1.at",156],["szene38.de",156],["t-online.de",156],["tagesspiegel.de",156],["taschenhirn.de",156],["techadvisor.co.uk",156],["techstage.de",156],["tele5.de",156],["teltarif.de",156],["testedich.*",156],["the-voice-of-germany.de",156],["thueringen24.de",156],["tichyseinblick.de",156],["tierfreund.co",156],["tiervermittlung.de",156],["torgranate.de",156],["transfermarkt.*",156],["trend.at",156],["truckscout24.*",156],["tv-media.at",156],["tvdigital.de",156],["tvinfo.de",156],["tvspielfilm.de",156],["tvtoday.de",156],["tvtv.*",156],["tz.de",[156,171]],["unicum.de",156],["unnuetzes.com",156],["unsere-helden.com",156],["unterhalt.net",156],["usinger-anzeiger.de",156],["usp-forum.de",156],["videogameszone.de",156],["vienna.at",156],["vip.de",156],["virtualnights.com",156],["vox.de",156],["wa.de",156],["wallstreet-online.de",[156,159]],["waz.de",156],["weather.us",156],["webfail.com",156],["weihnachten.me",156],["weihnachts-bilder.org",156],["weihnachts-filme.com",156],["welt.de",156],["weltfussball.at",156],["weristdeinfreund.de",156],["werkzeug-news.de",156],["werra-rundschau.de",156],["wetterauer-zeitung.de",156],["wetteronline.*",156],["wieistmeineip.*",156],["wiesbadener-kurier.de",156],["wiesbadener-tagblatt.de",156],["winboard.org",156],["windows-7-forum.net",156],["winfuture.de",[156,167]],["wintotal.de",156],["wlz-online.de",156],["wn.de",156],["wohngeld.org",156],["wolfenbuetteler-zeitung.de",156],["wolfsburger-nachrichten.de",156],["woman.at",156],["womenshealth.de",156],["wormser-zeitung.de",156],["woxikon.de",156],["wp.de",156],["wr.de",156],["wunderweib.de",156],["yachtrevue.at",156],["ze.tt",156],["zeit.de",156],["lecker.de",156],["meineorte.com",157],["osthessen-news.de",157],["techadvisor.com",157],["focus.de",157],["wetter.*",158],["herzporno.net",160],["pornhub-sexfilme.net",160],["pornojenny.net",160],["pornoleon.com",160],["deinesexfilme.com",161],["einfachtitten.com",161],["lesbenhd.com",161],["milffabrik.com",[161,223]],["porn-monkey.com",161],["porndrake.com",161],["pornhubdeutsch.net",161],["pornoaffe.com",161],["pornodavid.com",161],["pornoente.tv",[161,223]],["pornofisch.com",161],["pornofelix.com",161],["pornohammer.com",161],["pornohelm.com",161],["pornoklinge.com",161],["pornotom.com",[161,223]],["pornotommy.com",161],["pornovideos-hd.com",161],["pornozebra.com",[161,223]],["xhamsterdeutsch.xyz",161],["xnxx-sexfilme.com",161],["nu6i-bg-net.com",163],["kiaclub.cz",163],["khsm.io",163],["webcreator-journal.com",163],["msdos-games.com",163],["blocklayer.com",163],["animeshqip.org",163],["weknowconquer.com",163],["giff.cloud",163],["aquarius-horoscopes.com",164],["cancer-horoscopes.com",164],["dubipc.blogspot.com",164],["echoes.gr",164],["engel-horoskop.de",164],["freegames44.com",164],["fuerzasarmadas.eu",164],["gemini-horoscopes.com",164],["jurukunci.net",164],["krebs-horoskop.com",164],["leo-horoscopes.com",164],["maliekrani.com",164],["nklinks.click",164],["ourenseando.es",164],["pisces-horoscopes.com",164],["radio-en-direct.fr",164],["sagittarius-horoscopes.com",164],["scorpio-horoscopes.com",164],["singlehoroskop-loewe.de",164],["skat-karten.de",164],["skorpion-horoskop.com",164],["taurus-horoscopes.com",164],["the1security.com",164],["virgo-horoscopes.com",164],["zonamarela.blogspot.com",164],["yoima.hatenadiary.com",164],["kaystls.site",165],["ftuapps.dev",166],["studydhaba.com",166],["freecourse.tech",166],["victor-mochere.com",166],["papunika.com",166],["mobilanyheter.net",166],["prajwaldesai.com",[166,241]],["carscoops.com",167],["dziennik.pl",167],["eurointegration.com.ua",167],["flatpanelshd.com",167],["footballtransfer.com.ua",167],["footballtransfer.ru",167],["hoyme.jp",167],["issuya.com",167],["itainews.com",167],["iusm.co.kr",167],["logicieleducatif.fr",167],["mynet.com",[167,192]],["onlinegdb.com",167],["picrew.me",167],["pravda.com.ua",167],["reportera.co.kr",167],["sportanalytic.com",167],["sportsrec.com",167],["sportsseoul.com",167],["text-compare.com",167],["tweaksforgeeks.com",167],["wfmz.com",167],["worldhistory.org",167],["palabr.as",167],["motscroises.fr",167],["cruciverba.it",167],["w.grapps.me",167],["gazetaprawna.pl",167],["pressian.com",167],["raenonx.cc",[167,268]],["indiatimes.com",167],["missyusa.com",167],["aikatu.jp",167],["ark-unity.com",167],["cool-style.com.tw",167],["doanhnghiepvn.vn",167],["mykhel.com",167],["automobile-catalog.com",168],["motorbikecatalog.com",168],["maketecheasier.com",168],["mlbpark.donga.com",169],["jjang0u.com",170],["neowin.net",171],["newatlas.com",171],["razzball.com",171],["12thmanrising.com",171],["aroundthefoghorn.com",171],["arrowheadaddict.com",171],["badgerofhonor.com",171],["bamahammer.com",171],["beargoggleson.com",171],["beyondtheflag.com",171],["blackandteal.com",171],["blogredmachine.com",171],["bluemanhoop.com",171],["boltbeat.com",171],["bosoxinjection.com",171],["buffalowdown.com",171],["caneswarning.com",171],["catcrave.com",171],["chopchat.com",171],["climbingtalshill.com",171],["cubbiescrib.com",171],["dailyknicks.com",171],["dairylandexpress.com",171],["dawindycity.com",171],["dawnofthedawg.com",171],["detroitjockcity.com",171],["dodgersway.com",171],["ebonybird.com",171],["fansided.com",171],["gbmwolverine.com",171],["gmenhq.com",171],["hailfloridahail.com",171],["hardwoodhoudini.com",171],["horseshoeheroes.com",171],["housethathankbuilt.com",171],["huskercorner.com",171],["insidetheiggles.com",171],["jaysjournal.com",171],["justblogbaby.com",171],["kckingdom.com",171],["kingjamesgospel.com",171],["lakeshowlife.com",171],["lombardiave.com",171],["motorcitybengals.com",171],["musketfire.com",171],["nflspinzone.com",171],["ninernoise.com",171],["nugglove.com",171],["phinphanatic.com",171],["pistonpowered.com",171],["predominantlyorange.com",171],["ramblinfan.com",171],["redbirdrants.com",171],["reviewingthebrew.com",171],["riggosrag.com",171],["ripcityproject.com",171],["risingapple.com",171],["rumbunter.com",171],["scarletandgame.com",171],["section215.com",171],["sidelionreport.com",171],["slapthesign.com",171],["sodomojo.com",171],["stillcurtain.com",171],["stormininnorman.com",171],["stripehype.com",171],["thatballsouttahere.com",171],["thejetpress.com",171],["thelandryhat.com",171],["thepewterplank.com",171],["thesmokingcuban.com",171],["thevikingage.com",171],["thunderousintentions.com",171],["valleyofthesuns.com",171],["whodatdish.com",171],["yanksgoyard.com",171],["auto-swiat.pl",172],["download.kingtecnologia.com",173],["daemonanime.net",174],["bgmateriali.com",174],["daemon-hentai.com",175],["embedtv.net",176],["tinhte.vn",177],["app.simracing.gp",177],["forumdz.com",178],["zilinak.sk",178],["pdfaid.com",178],["bootdey.com",178],["mail.com",178],["moegirl.org.cn",178],["flix-wave.lol",178],["fmovies0.cc",178],["worthcrete.com",178],["infomatricula.pt",178],["my-code4you.blogspot.com",179],["vrcmods.com",180],["osuskinner.com",180],["osuskins.net",180],["pentruea.com",181],["mchacks.net",182],["why-tech.it",183],["compsmag.com",184],["tapetus.pl",185],["autoroad.cz",186],["brawlhalla.fr",186],["tecnobillo.com",186],["pokemon-project.com",186],["breatheheavy.com",187],["wenxuecity.com",188],["key-hub.eu",189],["fabioambrosi.it",190],["tattle.life",191],["emuenzen.de",191],["terrylove.com",191],["cidade.iol.pt",193],["fantacalcio.it",194],["hentaifreak.org",195],["hypebeast.com",196],["krankheiten-simulieren.de",197],["catholic.com",198],["techinferno.com",199],["ibeconomist.com",200],["bookriot.com",201],["purposegames.com",202],["globo.com",203],["latimes.com",203],["claimrbx.gg",204],["perelki.net",205],["vpn-anbieter-vergleich-test.de",206],["livingincebuforums.com",207],["tv247us.live",207],["paperzonevn.com",208],["alltechnerd.com",209],["malaysianwireless.com",210],["erinsakura.com",211],["infofuge.com",211],["freejav.guru",211],["novelmultiverse.com",211],["fritidsmarkedet.dk",212],["maskinbladet.dk",212],["15min.lt",213],["baddiehub.com",214],["mr9soft.com",215],["adult-sex-gamess.com",216],["hentaigames.app",216],["mobilesexgamesx.com",216],["mysexgamer.com",216],["porngameshd.com",216],["sexgamescc.com",216],["xnxx-sex-videos.com",216],["f2movies.to",217],["freeporncave.com",218],["tubsxxx.com",219],["manga18fx.com",220],["freebnbcoin.com",220],["sextvx.com",221],["muztext.com",222],["pornohans.com",223],["nursexfilme.com",223],["pornohirsch.net",223],["xhamster-sexvideos.com",223],["pornoschlange.com",223],["xhamsterdeutsch.*",223],["hdpornos.net",223],["gutesexfilme.com",223],["zona-leros.com",223],["charbelnemnom.com",224],["simplebits.io",225],["online-fix.me",226],["privatemoviez.*",227],["gamersdiscussionhub.com",227],["elahmad.com",228],["owlzo.com",229],["q1003.com",230],["blogpascher.com",231],["testserver.pro",232],["lifestyle.bg",232],["money.bg",232],["news.bg",232],["topsport.bg",232],["webcafe.bg",232],["schoolcheats.net",233],["mgnet.xyz",234],["advertiserandtimes.co.uk",235],["techsolveprac.com",236],["joomlabeginner.com",237],["askpaccosi.com",238],["largescaleforums.com",239],["dubznetwork.com",240],["dongknows.com",242],["traderepublic.community",243],["babia.to",244],["html5.gamemonetize.co",245],["code2care.org",246],["gmx.*",247],["yts-subs.net",248],["dlhd.sx",248],["xxxxsx.com",249],["ngontinh24.com",250],["idevicecentral.com",251],["mangacrab.com",253],["hortonanderfarom.blogspot.com",254],["viefaucet.com",255],["pourcesoir.in",255],["cloud-computing-central.com",256],["afk.guide",257],["businessnamegenerator.com",258],["derstandard.at",259],["derstandard.de",259],["rocketnews24.com",260],["soranews24.com",260],["youpouch.com",260],["gourmetscans.net",261],["ilsole24ore.com",262],["ipacrack.com",263],["infokik.com",264],["porhubvideo.com",266],["webseriessex.com",266],["panuvideo.com",[266,267]],["pornktubes.net",266],["deezer.com",268],["fosslinux.com",269],["shrdsk.me",270],["examword.com",271],["sempreupdate.com.br",271],["tribuna.com",272],["trendsderzukunft.de",273],["gal-dem.com",273],["lostineu.eu",273],["oggitreviso.it",273],["speisekarte.de",273],["mixed.de",273],["lightnovelspot.com",[274,275]],["novelpub.com",[274,275]],["webnovelpub.com",[274,275]],["hwzone.co.il",276],["nammakalvi.com",277],["igay69.com",277],["c2g.at",278],["terafly.me",278],["elamigos-games.com",278],["elamigos-games.net",278],["elamigosgames.org",278],["dktechnicalmate.com",279],["recipahi.com",279],["vpntester.org",280],["japscan.lol",281],["digitask.ru",282],["tempumail.com",283],["sexvideos.host",284],["camcaps.*",285],["10alert.com",286],["cryptstream.de",287],["nydus.org",287],["techhelpbd.com",288],["fapdrop.com",289],["cellmapper.net",290],["hdrez.com",291],["youwatch-serie.com",291],["russland.jetzt",291],["printablecreative.com",292],["peachprintable.com",292],["comohoy.com",293],["leak.sx",293],["paste.bin.sx",293],["pornleaks.in",293],["merlininkazani.com",293],["j91.asia",294],["jeniusplay.com",295],["indianyug.com",296],["rgb.vn",296],["needrom.com",297],["criptologico.com",298],["megadrive-emulator.com",299],["eromanga-show.com",300],["hentai-one.com",300],["hentaipaw.com",300],["10minuteemails.com",301],["luxusmail.org",301],["w3cub.com",302],["bangpremier.com",303],["nyaa.iss.ink",304],["drivebot.*",305],["thenextplanet1.*",306],["tnp98.xyz",306],["techedubyte.com",307],["poplinks.*",308],["tickzoo.tv",309],["oploverz.*",309],["memedroid.com",310],["karaoketexty.cz",311],["filmizlehdfilm.com",312],["filmizletv.*",312],["fullfilmizle.cc",312],["gofilmizle.net",312],["resortcams.com",313],["cheatography.com",313],["sonixgvn.net",314],["autoscout24.*",315],["mjakmama24.pl",316],["cheatermad.com",317],["work.ink",318],["ville-ideale.fr",319],["brainly.*",320],["eodev.com",320],["xfreehd.com",322],["freethesaurus.com",323],["thefreedictionary.com",323],["fm-arena.com",324],["tradersunion.com",325],["tandess.com",326],["allosurf.net",326],["spontacts.com",327],["dankmemer.lol",328],["getexploits.com",329],["fplstatistics.com",330],["breitbart.com",331],["salidzini.lv",332],["cryptorank.io",[333,334]],["qqwebplay.xyz",335],["molbiotools.com",336],["vods.tv",337],["18xxx.xyz",[338,373]],["raidrush.net",339],["xnxxcom.xyz",340],["videzz.net",341],["spambox.xyz",342],["dreamdth.com",343],["freemodsapp.in",343],["onlytech.com",343],["en-thunderscans.com",344],["infinityscans.xyz",345],["infinityscans.net",345],["infinityscans.org",345],["historicaerials.com",346],["iqksisgw.xyz",347],["caroloportunidades.com.br",348],["coempregos.com.br",348],["foodiesgallery.com",348],["vikatan.com",349],["camhub.world",350],["omuzaani.me",351],["mma-core.*",352],["pouvideo.*",353],["povvideo.*",353],["povw1deo.*",353],["povwideo.*",353],["powv1deo.*",353],["powvibeo.*",353],["powvideo.*",353],["powvldeo.*",353],["op.gg",354],["teracourses.com",355],["servustv.com",[356,357]],["freevipservers.net",358],["streambtw.com",359],["qrcodemonkey.net",360],["streamup.ws",361],["tv-films.co.uk",362],["cool--web-de.translate.goog",[363,364]],["gps--cache-de.translate.goog",[363,364]],["web--spiele-de.translate.goog",[363,364]],["fun--seiten-de.translate.goog",[363,364]],["photo--alben-de.translate.goog",[363,364]],["wetter--vorhersage-de.translate.goog",[363,364]],["coolsoftware-de.translate.goog",[363,364]],["kryptografie-de.translate.goog",[363,364]],["cool--domains-de.translate.goog",[363,364]],["net--tours-de.translate.goog",[363,364]],["such--maschine-de.translate.goog",[363,364]],["qul-de.translate.goog",[363,364]],["mailtool-de.translate.goog",[363,364]],["c--ix-de.translate.goog",[363,364]],["softwareengineer-de.translate.goog",[363,364]],["net--tools-de.translate.goog",[363,364]],["hilfen-de.translate.goog",[363,364]],["45er-de.translate.goog",[363,364]],["cooldns-de.translate.goog",[363,364]],["hardware--entwicklung-de.translate.goog",[363,364]],["bgsi.gg",365],["kio.ac",366],["friv.com",367],["sextb.*>>",368],["nepalieducate.com",369],["tsz.com.np",369],["idlixku.com",370],["freegames.com",371],["levante-emv.com",372],["mallorcazeitung.es",372],["regio7.cat",372],["superdeporte.es",372],["laopiniondezamora.es",372],["laopiniondemurcia.es",372],["laopiniondemalaga.es",372],["laopinioncoruna.es",372],["lacronicabadajoz.com",372],["informacion.es",372],["farodevigo.es",372],["emporda.info",372],["elperiodicomediterraneo.com",372],["elperiodicoextremadura.com",372],["epe.es",372],["elperiodicodearagon.com",372],["eldia.es",372],["elcorreoweb.es",372],["diariodemallorca.es",372],["diariodeibiza.es",372],["diariocordoba.com",372],["diaridegirona.cat",372],["elperiodico.com",372],["laprovincia.es",372],["4tube.live",373],["nxxn.live",373],["redtub.live",373],["olympustaff.com",374],["imleagues.com",375],["loudountimes.com",376],["santafenewmexican.com",376],["tdtnews.com",376],["dataunlocker.com",377]]);
const exceptionsMap = new Map([["vvid30c.*",[133]]]);
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
    try { preventSetTimeout(...argsList[i]); }
    catch { }
}

/******************************************************************************/

// End of local scope
})();

void 0;
