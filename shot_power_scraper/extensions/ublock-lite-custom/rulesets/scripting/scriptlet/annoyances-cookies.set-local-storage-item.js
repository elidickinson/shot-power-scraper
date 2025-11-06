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

// ruleset: annoyances-cookies

// Important!
// Isolate from global scope

// Start of local scope
(function uBOL_setLocalStorageItem() {

/******************************************************************************/

function setLocalStorageItem(key = '', value = '') {
    setLocalStorageItemFn('local', false, key, value);
}

function setLocalStorageItemFn(
    which = 'local',
    trusted = false,
    key = '',
    value = '',
) {
    if ( key === '' ) { return; }

    // For increased compatibility with AdGuard
    if ( value === 'emptyArr' ) {
        value = '[]';
    } else if ( value === 'emptyObj' ) {
        value = '{}';
    }

    const trustedValues = [
        '',
        'undefined', 'null',
        '{}', '[]', '""',
        '$remove$',
        ...getSafeCookieValuesFn(),
    ];

    if ( trusted ) {
        if ( value.includes('$now$') ) {
            value = value.replaceAll('$now$', Date.now());
        }
        if ( value.includes('$currentDate$') ) {
            value = value.replaceAll('$currentDate$', `${Date()}`);
        }
        if ( value.includes('$currentISODate$') ) {
            value = value.replaceAll('$currentISODate$', (new Date()).toISOString());
        }
    } else {
        const normalized = value.toLowerCase();
        const match = /^("?)(.+)\1$/.exec(normalized);
        const unquoted = match && match[2] || normalized;
        if ( trustedValues.includes(unquoted) === false ) {
            if ( /^-?\d+$/.test(unquoted) === false ) { return; }
            const n = parseInt(unquoted, 10) || 0;
            if ( n < -32767 || n > 32767 ) { return; }
        }
    }

    try {
        const storage = self[`${which}Storage`];
        if ( value === '$remove$' ) {
            const safe = safeSelf();
            const pattern = safe.patternToRegex(key, undefined, true );
            const toRemove = [];
            for ( let i = 0, n = storage.length; i < n; i++ ) {
                const key = storage.key(i);
                if ( pattern.test(key) ) { toRemove.push(key); }
            }
            for ( const key of toRemove ) {
                storage.removeItem(key);
            }
        } else {
            storage.setItem(key, `${value}`);
        }
    } catch {
    }
}

function getSafeCookieValuesFn() {
    return [
        'accept', 'reject',
        'accepted', 'rejected', 'notaccepted',
        'allow', 'disallow', 'deny',
        'allowed', 'denied',
        'approved', 'disapproved',
        'checked', 'unchecked',
        'dismiss', 'dismissed',
        'enable', 'disable',
        'enabled', 'disabled',
        'essential', 'nonessential',
        'forbidden', 'forever',
        'hide', 'hidden',
        'necessary', 'required',
        'ok',
        'on', 'off',
        'true', 't', 'false', 'f',
        'yes', 'y', 'no', 'n',
        'all', 'none', 'functional',
        'granted', 'done',
        'decline', 'declined',
        'closed', 'next', 'mandatory',
        'disagree', 'agree',
    ];
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
const argsList = [["cookieConsent","{}"],["CookieConsent--hideCookieConsent","true"],["consent","false"],["duckaiHasAgreedToTerms","true"],["areCookiesAccepted","true"],["cookieConsentV2","1"],["gdpr","0"],["room-welcome-ack-v1","1"],["COOKIE_CHECK","false"],["lscache-klbq-bucket-scceptCookie","true"],["analytics-consent","accepted"],["cookie-consent","\"denied\""],["cookieConsent","granted"],["Express.cookie_agreement_shown","true"],["cookies-agreed-sellers-external-HC","true"],["hide-legal","1"],["cookie_consent","denied"],["cookies-toast-shown","true"],["show_consent_modal","1"],["SITE_2609202-COOKIE-BANNER","1"],["COOKIE_CONSENT","no"],["cookie_consent","true"],["df-cookies-allowed","true"],["cookie_consent","no"],["mmkv.default\\ANONYMOUS_ACCEPT_COOKIE","true"],["isCookieAccepted","true"],["cookies-pref","[]"],["cookiesAccepted","false"],["store-cookie-consent","accepted"],["_ccpa_analytics","false"],["_ccpa_marketing","false"],["_ccpa_personal","false"],["psh:cookies-other","false"],["no-cookie-notice-dismissed","true"],["psh:cookies-seen","true"],["psh:cookies-social","true"],["cookiesAccepted","true"],["isAcceptedCookie","1"],["cookiePolicy","true"],["cookiesAccepted","yes"],["cookies_enabled","true"],["acceptedAllCookies","false"],["cookiePreference","essential"],["cookie-consent-banner","declined"],["allowed_cookies","true"],["cookie-consent","false"],["consents-analytics","false"],["vdk-required-enabled","true"],["vdk-iframe-enabled","true"],["vdk-status","accept"],["cookie_consent","granted"],["cookieBarVisible","false"],["HAS_AGREE_POLICY","true"],["cookie-accepted","1"],["CustomCookieBannerAcceptIntent","true"],["pc-cookie-accepted","true"],["pc-cookie-technical-accepted","true"],["cookie-consent","rejected"],["owf_agree_cookie_policy","true"],["cookieConsent","accepted"],["allowFunctionalCookies","false"],["cookieClosed","true"],["explicitCookieAccept-24149","true"],["keeper_cookie_consent","true"],["cookie_accepted","true"],["consentLevel","1"],["cookies-val","accepted"],["201805-policy|accepted","1"],["GDPR-fingerprint:accepted","true"],["CPCCookies","true"],["privacyModalSeen","true"],["LGPDconsent","1"],["isCookiePoliceAccepted","1"],["HAS_ACCEPTED_PRIVACY_POLICY","true"],["cookiesAceptadas","true"],["privacy.com.br","accepted"],["supabase-consent-ph","false"],["cookieConsent","essential"],["has-seen-ccpa-notice","true"],["wbx__cookieAccepted","true"],["show_cookies_popup","false"],["modal_cookies","1"],["trainingDataConsent","true"],["cookieConsent","false"],["zglobal_Acookie_optOut","3"],["cookie","true"],["cookies_view","true"],["gdprConsent","false"],["framerCookiesDismissed","true"],["vue-cookie-accept-decline-cookiePanel","accept"],["cookies-consent-accepted","true"],["user-cookies-setting","1"],["COOKIE_AUTHORITY_QUERY_V2","1"],["ignore_cookie_warn","true"],["CerezUyariGosterildi","true"],["cookies-product","NO"],["showCookies","NO"],["localConsent","true"],["acceptedCookies","true"],["isNotificationDisplayed","true"],["COOKIE_BANNER_CLICKED","true"],["cookies-eu-statistics","false"],["cookies-eu-necessary","true"],["cookieStatus","rejected"],["consent","true"],["cookiePreference","required"],["technikmuseum-required-enabled","true"],["ctu-cm-n","1"],["ctu-cm-a","0"],["ctu-cm-m","0"],["cookieAndRecommendsAgreement","true"],["cookiebanner-active","false"],["tracking-state-v2","deny"],["cookieConsent","true"],["202306151200.shown.production","true"],["consent","[]"],["cookiebanner:extMedia","false"],["cookiebanner:statistic","false"],["consentAccepted","true"],["marketingConsentAccepted","false"],["consentMode","1"],["uninavIsAgreeCookie","true"],["cookieConsent","denied"],["cookieChoice","rejected"],["adsAccepted","false"],["analyticsAccepted","false"],["analytics_gdpr_accept","yes"],["youtube_gdpr_accept","yes"],["Analytics:accepted","false"],["GDPR:accepted","true"],["cookie_usage_acknowledged_2","1"],["a_c","true"],["userDeniedCookies","1"],["hasConsent","false"],["viewedCookieConsent","true"],["dnt_message_shown","1"],["necessaryConsent","true"],["marketingConsent","false"],["personalisationConsent","false"],["open_modal_update_policy","1"],["cookieinfo","1"],["cookies","1"],["cookieAccepted","true"],["necessary_cookie_confirmed","true"],["ccb_contao_token_1","1"],["cookies","0"],["cookies_accepted_6pzworitz8","true"],["rgpd.consent","1"],["_lukCookieAgree","2"],["cookiesAllowed","false"],["cookiePreference","1"],["artisan_acceptCookie","true"],["cookies_policy_acceptance","denied"],["SAFE__analyticsPreference","false"],["termsOfUseAccepted","true"],["agreeCookie","true"],["lgpd-agree","1"],["cookieIsAccepted","true"],["cookieAllowed","false"],["cookie_usage_accepted","1"],["cookieBannerShown","true"],["cookiesConsent","1"],["cookie_acceptance","true"],["analytics_cookies_acceptance","true"],["ns_cookies","1"],["gdpr","deny"],["c","false"],["cookies-preference","1"],["cookiesAcknowledged","1"],["hasConsentedPH","no"],["cookie_consent","accepted"],["gtag.consent.option","1"],["cps28","1"],["PrivacyPolicy[][core]","forbidden"],["PrivacyPolicy[][maps]","forbidden"],["PrivacyPolicy[][videos]","forever"],["PrivacyPolicy[][readSpeaker]","forbidden"],["PrivacyPolicy[][tracking]","forbidden"],["showCookieUse","false"],["terms","accepted"],["z_cookie_consent","true"],["StorageMartCookiesPolicySeen","true"],["bunq:CookieConsentStore:isBannerVisible","false"],["accepted-cookies","[]"],["ngx-webstorage|cookies","false"],["app_gdpr_consent","1"],["alreadyAcceptCookie","true"],["isCookiesAccepted","true"],["cookies","no"],["cookies-policy-accepted","true"],["cookie_prompt_times","1"],["last_prompt_time","1"],["sup_gdpr_cookie","accepted"],["gdpr_cookie","accepted"],["cn","true"],["consent_popup","1"],["COOKIE_CONSENT","false"],["cookie-consent-declined-version","1"],["Do-not-share","true"],["allow-cookies","false"],["should_display_cookie_banner_v2","false"],["zora-discover-14-03-23","false"],["connect-wallet-legal-consent","true"],["cookiesMin","1"],["cb-accept-cookie","true"],["cookie-permission","false"],["cookies","true"],["ROCUMENTS.cookieConsent","true"],["bcCookieAccepted","true"],["CMP:personalisation","1"],["pcClosedOnce","true"],["textshuttle_cookie","false"],["cookies-notification-message-is-hidden","true"],["cookieBanner","false"],["cookieBanner","true"],["banner","true"],["isAllowCookies","true"],["gtag_enabled","1"],["cvcConsentGiven","true"],["terms","true"],["cookie_accept","true"],["Pechinchou:CookiesModal","true"],["hub-cp","true"],["cookiePolicyAccepted","yes"],["cookie_usage_acknowledged_2","true"],["cookies_necessary_consent","true"],["cookies_marketing_consent","false"],["cookies_statistics_consent","false"],["wu.ccpa-toast-viewed","true"],["closed","true"],["dnt","1"],["dnt_a","1"],["makerz_allow_consentmgr","0"],["SHOW_COOKIE_BANNER","no"],["CookiesConsent","1"],["hasAnalyticalCookies","false"],["hasStrictlyNecessaryCookies","true"],["amCookieBarFirstShow","1"],["acceptedCookies","false"],["viewedCookieBanner","true"],["accept_all_cookies","false"],["isCookies","1"],["isCookie","Yes"],["cookieconsent_status","false"],["user_cookie","1"],["ka:4:legal-updates","true"],["cok","true"],["cookieMessage","true"],["soCookiesPolicy","1"],["GDPR:RBI:accepted","false"],["contao-privacy-center.hidden","1"],["cookie_consent","false"],["cookiesAgree","true"],["ytsc_accepted_cookies","true"],["safe-storage/v1/tracking-consent/trackingConsentMarketingKey","false"],["safe-storage/v1/tracking-consent/trackingConsentAdvertisingKey","false"],["safe-storage/v1/tracking-consent/trackingConsentAnalyticsKey","false"],["agreeToCookie","false"],["AI Alliance_ReactCookieAcceptance_hasSetCookies","true"],["firstVisit","false"],["2020-04-05","1"],["dismissed","true"],["SET_COOKIES_APPROVED","true"],["hasAcceptedCookies","true"],["isCookiesNotificationHidden","true"],["agreed-cookies","true"],["consentCookie","true"],["SWCOOKIESACC","1"],["hasAcceptedCookieNotice","true"],["fb-cookies-accepted","false"],["is_accept_cookie","true"],["accept-jove-cookie","1"],["cookie_consent_bar_value","true"],["pxdn_cookie_consent","true"],["akasha__cookiePolicy","true"],["QMOptIn","false"],["safe.global","false"],["cookie_banner:hidden","true"],["accept_cookie_policy","true"],["cookies_accepted","true"],["cookies-selected","true"],["cookie-notice-dismissed","true"],["accepts-cookie-notice","true"],["dismissedPrivacyCookieMessage","1"],["allowCookies","allowed"],["cookies_policy_status","true"],["cookies-accepted","true"],["allowCookies","true"],["cookie_consent","1"],["accepted-cookies","true"],["cookies-consent","0"],["cookieBannerRead","true"],["acceptCookie","0"],["cookieBannerReadDate","1"],["privacy-policy-accepted","true"],["accepted_cookies","true"],["accepted_cookie","true"],["cookie-consent","true"],["consentManager_shown","true"],["consent_necessary","true"],["consent_performance","false"],["cookie-closed","true"],["cookie-accepted","false"],["consent_analytics","false"],["consent_granted","true"],["consent_marketing","false"],["cookie-accepted","true"],["cookieConsent","1"],["enableCookieBanner","false"],["byFoodCookiePolicyRequire","false"],["ascookie--decision","true"],["isAcceptCookiesNew","true"],["isAcceptCookie","true"],["isAcceptCookie","false"],["marketing","false"],["technical","true","","reload","1"],["analytics","false"],["otherCookie","true"],["saveCookie","true"],["userAcceptsCookies","1"],["grnk-cookies-accepted","true"],["acceptCookies","no"],["acceptCookies","true"],["has-dismissed","1"],["hasAcceptedGdpr","true"],["lw-accepts-cookies","true"],["cookies-accept","true"],["load-scripts-v2","2"],["acceptsAnalyticsCookies","false"],["acceptsNecessaryCookies","true"],["display_cookie_modal","false"],["pg-accept-cookies","true"],["__EOBUWIE__consents_accepted","true","","reload","1"],["canada-cookie-acknowledge","1"],["FP_cookiesAccepted","true"],["VISITED_0","true"],["OPTIONAL_COOKIES_ACCEPTED_0","true"],["storagePermission","true"],["set_cookie_stat","false"],["set_cookie_tracking","false"],["UMP_CONSENT_NOTIFICATION","true"],["cookie-consent","1"],["userConsented","false"],["cookieConsent","necessary"],["gdpr-done","true"],["isTrackingAllowed","false"],["legalsAccepted","true"],["COOKIE_CONSENT_STATUS_4124","\"dismissed\""],["cookie-policy","approve"],["spaseekers:cookie-decision","accepted"],["policyAccepted","true"],["PrivacyPolicy[][core]","forever"],["consentBannerLastShown","1"],["flipdish-cookies-preferences","necessary"],["consentInteraction","true"],["cookie-notice-accepted-version","1"],["cookieConsentGiven","1"],["cookie-banner-accepted","true"]];
const hostnamesMap = new Map([["rg.ru",0],["teamtailor.com",1],["dewesoft.com",2],["duckduckgo.com",3],["hospihousing.com",4],["mastersintime.com",5],["watch.co.uk",5],["inverto.tv",6],["theroom.lol",7],["titantvguide.com",8],["strinova.com",9],["thai-novel.com",10],["todoist.com",11],["notthebee.com",12],["bcs-express.ru",13],["seller.wildberries.ru",14],["wifiman.com",15],["vibeslist.ai",16],["shlib.life",17],["slashlib.me",17],["mangalib.me",17],["anilib.me",17],["animelib.org",17],["hentailib.me",17],["hentailib.org",17],["mangalib.org",17],["ranobelib.me",17],["negrasport.pl",18],["pancernik.eu",[18,22]],["mobilelegends.com",19],["manuals.annafreud.org",20],["v3.ketogo.app",21],["ketogo.app",21],["schneideranwaelte.de",21],["traefik.io",21],["gesundheitsmanufaktur.de",[22,105]],["open24.ee",22],["granola.ai",23],["polar.sh",23],["posthog.com",23],["hatchet.run",23],["zeta-ai.io",24],["fiyat.mercedes-benz.com.tr",25],["sportbooking.info",26],["photo.codes",27],["filmzie.com",27],["granado.com.br",28],["sunnyside.shop",[29,30,31]],["nhnieuws.nl",[32,34,35]],["omroepbrabant.nl",[32,34,35]],["cape.co",33],["asianet.co.id",36],["p2p.land",36],["netbank.avida.no",36],["bo3.gg",36],["gs1.se",[36,60]],["puregoldprotein.com",[36,124,125]],["spectrumtherapeutics.com",36],["thingtesting.com",36],["streamclipsgermany.de",36],["kundenportal.harzenergie.de",36],["giselles.ai",37],["i-fundusze.pl",38],["improvethenews.org",38],["plente.com",38],["movies4us.*",38],["popcornmovies.to",38],["arkanium.serveminecraft.net",39],["bananacraft.serveminecraft.net",39],["myoffers.smartbuy.hdfcbank.com",40],["grass.io",[41,42]],["lustery.com",43],["ecoints.com",44],["emergetools.com",45],["receptagemini.pl",46],["bw.vdk.de",[47,48,49]],["search.odin.io",50],["gdh.digital",51],["popmart.com",52],["rozklady.bielsko.pl",53],["typeform.com",54],["erlus.com",[55,56]],["bettrfinancing.com",57],["sf-express.com",58],["min.io",59],["lemwarm.com",61],["form.fillout.com",62],["keepersecurity.com",63],["esto.eu",64],["ctol.digital",64],["beterbed.nl",65],["crt.hr",66],["code.likeagirl.io",67],["engineering.mixpanel.com",67],["betterprogramming.pub",67],["medium.com",67],["500ish.com",67],["gitconnected.com",67],["bettermarketing.pub",67],["diylifetech.com",67],["thebolditalic.com",67],["writingcooperative.com",67],["fanfare.pub",67],["betterhumans.pub",67],["fvd.nl",68],["cpc2r.ch",69],["metamask.io",70],["chavesnamao.com.br",71],["anhanguera.com",72],["bhaskar.com",73],["novaventa.com",74],["privacy.com.br",75],["supabase.com",76],["app.getgrass.io",77],["sanluisgarbage.com",78],["wildberries.ru",79],["cryptorank.io",80],["springmerchant.com",81],["veed.io",82],["deribit.com",83],["dorkgpt.com",83],["kyutai.org",83],["varusteleka.com",83],["lazyrecords.app",83],["unmute.sh",83],["zoho.com",84],["femibion.rs",85],["nove.fr",85],["metro1.com.br",85],["villagrancanaria.com",86],["baic.cz",87],["mollie.com",88],["bunq.com",88],["framer.com",88],["inceptionlabs.ai",88],["zave.it",88],["tower.dev",88],["fleksberegner.dk",89],["duty.travel.cl",90],["solscan.io",91],["connorduffy.abundancerei.com",92],["bc.gamem",93],["akkushop-turkiye.com.tr",94],["k33.com",[95,96]],["komdigi.go.id",97],["fijiairways.com",98],["planner.kaboodle.co.nz",99],["pedalcommander.*",100],["sekisuialveo.com",[101,102]],["rightsize.dk",103],["random-group.olafneumann.org",104],["espadrij.com",105],["hygiene-shop.eu",105],["technikmuseum.berlin",106],["cvut.cz",[107,108,109]],["r-ulybka.ru",110],["voltadol.at",111],["evium.de",112],["hiring.amazon.com",113],["comnet.com.tr",113],["gpuscout.nl",113],["remanga.org",113],["parrotsec.org",113],["estrelabet.bet.br",113],["cricketgully.com",113],["shonenjumpplus.com",114],["engeldirekt.de",115],["haleon-gebro.at",[116,117]],["happyplates.com",[118,119]],["ickonic.com",120],["abs-cbn.com",121],["news.abs-cbn.com",121],["opmaatzagen.nl",122],["mundwerk-rottweil.de",122],["sqlook.com",123],["adef-emploi.fr",[126,127]],["lumieresdelaville.net",[126,127]],["ccaf.io",[128,129]],["dbschenkerarkas.com.tr",130],["dbschenker-seino.jp",130],["dbschenker.com",[130,224]],["scinapse.io",131],["uc.pt",132],["bennettrogers.mysight.uk",133],["snipp.gg",133],["leafly.com",134],["geizhals.at",135],["geizhals.de",135],["geizhals.eu",135],["cenowarka.pl",135],["skinflint.co.uk",135],["webhallen.com",[136,137,138]],["olx.com.br",139],["unobike.com",140],["mod.io",141],["passport-photo.online",142],["mojmaxtv.hrvatskitelekom.hr",142],["rodrigue-app.ct.ws",142],["tme.eu",143],["mein-osttirol.rocks",144],["tennessine.co.uk",145],["ultraleds.co.uk",146],["greubelforsey.com",147],["lukify.app",148],["studiobookr.com",149],["getgrass.io",150],["artisan.co",151],["mobilefuse.com",152],["safe.global",[153,276]],["data.carbonmapper.org",154],["avica.link",155],["madeiramadeira.com.br",156],["sberdisk.ru",157],["column.com",158],["iqoption.com",159],["dopesnow.com",160],["montecwear.com",160],["romeo.com",161],["sonyliv.com",[162,163]],["cwallet.com",164],["oneskin.co",165],["telemetr.io",166],["near.org",167],["near.ai",167],["dev.near.org",168],["jito.network",169],["jito.wtf",169],["goodpods.com",170],["pngtree.com",[171,172]],["rhein-pfalz-kreis.de",[173,174,175,176,177]],["idar-oberstein.de",[173,174,175,176]],["vogelsbergkreis.de",[173,174,175,176]],["chamaeleon.de",[175,351]],["v2.xmeye.net",178],["venom.foundation",179],["canonvannederland.nl",180],["my-account.storage-mart.com",181],["web.bunq.com",182],["lifesum.com",183],["home.shortcutssoftware.com",184],["klimwinkel.nl",185],["markimicrowave.com",186],["aerolineas.com.ar",187],["5sim.net",187],["fold.dev",188],["mojposao.hr",189],["temu.com",[190,191]],["supreme.com",[192,193]],["g-star.com",194],["sawren.pl",195],["ultrahuman.com",196],["optionsgroup.com",197],["withpersona.com",[198,199]],["core.app",[200,202]],["zora.co",201],["kokku-online.de",203],["cuba-buddy.de",204],["datamask.app",205],["humandataincome.com",205],["crealitycloud.com",206],["triumphtechnicalinformation.com",207],["businessclass.com",208],["livsstil.se",209],["schneidewind-immobilien.de",210],["textshuttle.com",211],["simpleswap.io",212],["wales.nhs.attendanywhere.com",213],["anonpaste.pw",214],["sacal.it",214],["astondevs.ru",215],["gonxt.com",216],["geomiq.com",217],["bbc.com",218],["galaxy.com",219],["ticketmelon.com",220],["pechinchou.com.br",221],["thehub21.com",222],["archiup.com",223],["autoride.cz",[225,226,227]],["autoride.es",[225,226,227]],["autoride.io",[225,226,227]],["autoride.sk",[225,226,227]],["wunderground.com",228],["baselime.io",229],["eversports.de",[230,231]],["makerz.me",232],["reebok.eu",233],["alfa.com.ec",234],["rts.com.ec",234],["tropicalida.com.ec",234],["owgr.com",[235,236]],["beermerchants.com",237],["saamexe.com",[238,239]],["helium.com",238],["blommerscoffee.shipping-portal.com",238],["app.bionic-reading.com",240],["nloto.ru",241],["swisstours.com",242],["librinova.com",243],["format.bike",244],["khanacademy.org",245],["etelecinema.hu",246],["konicaminolta.com",247],["soquest.xyz",248],["region-bayreuth.de",249],["bahnland-bayern.de",250],["eezy.nrw",250],["nationalexpress.de",250],["sumupbookings.com",251],["chipcitycookies.com",251],["6amgroup.com",251],["go.bkk.hu",251],["worldlibertyfinancial.com",251],["happiful.com",251],["moondao.com",251],["bazaartracker.com",252],["subscribercounter.com",253],["app.klarna.com",[254,255,256]],["instantspoursoi.fr",257],["thealliance.ai",258],["librumreader.com",259],["visnos.com",260],["polypane.app",261],["changelly.com",262],["glose.com",263],["yellow.systems",264],["renebieder.com",265],["goodram.com",266],["starwalk.space",267],["vitotechnology.com",267],["codedead.com",268],["studiofabiobiesel.com",269],["fydeos.com",270],["fydeos.io",270],["jove.com",271],["argent.xyz",272],["pixeden.com",273],["akasha.org",274],["ashleyfurniture.com",275],["jibjab.com",277],["vietjetair.com",278],["kick.com",279],["cora-broodjes.nl",280],["jimdosite.com",280],["worstbassist.com",280],["evernote.com",[281,282,355]],["octopusenergy.co.jp",283],["findmcserver.com",284],["cityfalcon.ai",285],["digitalparking.city",286],["mediathekviewweb.de",287],["solana.com",288],["ef.co.id",289],["alohafromdeer.com",290],["fwd.com",[291,293]],["everywhere.game",292],["geotastic.net",294],["garageproject.co.nz",295],["tattoodo.com",[295,296]],["jmonline.com.br",297],["atlas.workland.com",297],["virginexperiencedays.co.uk",297],["emag.berliner-woche.de",[298,299,300]],["nordkurier.de",[298,299,300]],["everest-24.pl",[301,302]],["operaneon.com",[303,304,305]],["abastible.cl",306],["sneakerfreaker.com",307],["cryptofalka.hu",307],["walmart.ca",308],["byfood.com",309],["andsafe.de",310],["edostavka.by",311],["emall.by",311],["ishoppurium.com",312],["baseblocks.tenereteam.com",313],["onexstore.pl",[314,315,316]],["revanced.app",316],["evropochta.by",[317,318]],["inselberlin.de",319],["gronkh.tv",320],["adfilteringdevsummit.com",321],["dailyrevs.com",322],["dsworks.ru",322],["daraz.com",323],["learngerman.dw.com",324],["leeway.tech",325],["gostanford.com",326],["namensetiketten.de",327],["drafthound.com",[328,329]],["wokularach.pl",330],["bidup.amtrak.com",331],["eschuhe.de",332],["zeglins.com",333],["flyingpapers.com",334],["beta.character.ai",[335,336]],["bittimittari.fi",337],["aida64.co.uk",[338,339]],["aida64.com.ua",[338,339]],["aida64.de",[338,339]],["aida64.hu",[338,339]],["aida64.it",[338,339]],["aida64russia.com",[338,339]],["116.ru",340],["14.ru",340],["161.ru",340],["164.ru",340],["173.ru",340],["178.ru",340],["26.ru",340],["29.ru",340],["35.ru",340],["43.ru",340],["45.ru",340],["48.ru",340],["51.ru",340],["53.ru",340],["56.ru",340],["59.ru",340],["60.ru",340],["63.ru",340],["68.ru",340],["71.ru",340],["72.ru",340],["74.ru",340],["76.ru",340],["86.ru",340],["89.ru",340],["93.ru",340],["chita.ru",340],["e1.ru",340],["fontanka.ru",340],["ircity.ru",340],["izh1.ru",340],["mgorsk.ru",340],["msk1.ru",340],["ngs.ru",340],["ngs22.ru",340],["ngs24.ru",340],["ngs42.ru",340],["ngs55.ru",340],["ngs70.ru",340],["nn.ru",340],["sochi1.ru",340],["sterlitamak1.ru",340],["tolyatty.ru",340],["ufa1.ru",340],["v1.ru",340],["vladivostok1.ru",340],["voronezh1.ru",340],["ya62.ru",340],["116117.fi",341],["pjspub.com",342],["autodude.dk",343],["autodude.fi",343],["autodude.no",343],["autodude.se",343],["valostore.fi",343],["valostore.no",343],["valostore.se",343],["vivantis.*",344],["vivantis-shop.at",344],["krasa.cz",344],["auf1.tv",345],["wesendit.com",346],["hatch.co",347],["haberturk.com",348],["spaseekers.com",349],["incomeshares.com",350],["surnamedb.com",352],["pizzadelight-menu.co.uk",353],["ioplus.nl",354],["lahella.fi",356],["healf.com",357]]);
const exceptionsMap = new Map([]);
const hasEntities = true;
const hasAncestors = false;

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
    try { setLocalStorageItem(...argsList[i]); }
    catch { }
}

/******************************************************************************/

// End of local scope
})();

void 0;
