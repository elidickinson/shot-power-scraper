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
(function uBOL_setConstant() {

/******************************************************************************/

function setConstant(
    ...args
) {
    setConstantFn(false, ...args);
}

function setConstantFn(
    trusted = false,
    chain = '',
    rawValue = ''
) {
    if ( chain === '' ) { return; }
    const safe = safeSelf();
    const logPrefix = safe.makeLogPrefix('set-constant', chain, rawValue);
    const extraArgs = safe.getExtraArgs(Array.from(arguments), 3);
    function setConstant(chain, rawValue) {
        const trappedProp = (( ) => {
            const pos = chain.lastIndexOf('.');
            if ( pos === -1 ) { return chain; }
            return chain.slice(pos+1);
        })();
        const cloakFunc = fn => {
            safe.Object_defineProperty(fn, 'name', { value: trappedProp });
            return new Proxy(fn, {
                defineProperty(target, prop) {
                    if ( prop !== 'toString' ) {
                        return Reflect.defineProperty(...arguments);
                    }
                    return true;
                },
                deleteProperty(target, prop) {
                    if ( prop !== 'toString' ) {
                        return Reflect.deleteProperty(...arguments);
                    }
                    return true;
                },
                get(target, prop) {
                    if ( prop === 'toString' ) {
                        return function() {
                            return `function ${trappedProp}() { [native code] }`;
                        }.bind(null);
                    }
                    return Reflect.get(...arguments);
                },
            });
        };
        if ( trappedProp === '' ) { return; }
        const thisScript = document.currentScript;
        let normalValue = validateConstantFn(trusted, rawValue, extraArgs);
        if ( rawValue === 'noopFunc' || rawValue === 'trueFunc' || rawValue === 'falseFunc' ) {
            normalValue = cloakFunc(normalValue);
        }
        let aborted = false;
        const mustAbort = function(v) {
            if ( trusted ) { return false; }
            if ( aborted ) { return true; }
            aborted =
                (v !== undefined && v !== null) &&
                (normalValue !== undefined && normalValue !== null) &&
                (typeof v !== typeof normalValue);
            if ( aborted ) {
                safe.uboLog(logPrefix, `Aborted because value set to ${v}`);
            }
            return aborted;
        };
        // https://github.com/uBlockOrigin/uBlock-issues/issues/156
        //   Support multiple trappers for the same property.
        const trapProp = function(owner, prop, configurable, handler) {
            if ( handler.init(configurable ? owner[prop] : normalValue) === false ) { return; }
            const odesc = safe.Object_getOwnPropertyDescriptor(owner, prop);
            let prevGetter, prevSetter;
            if ( odesc instanceof safe.Object ) {
                owner[prop] = normalValue;
                if ( odesc.get instanceof Function ) {
                    prevGetter = odesc.get;
                }
                if ( odesc.set instanceof Function ) {
                    prevSetter = odesc.set;
                }
            }
            try {
                safe.Object_defineProperty(owner, prop, {
                    configurable,
                    get() {
                        if ( prevGetter !== undefined ) {
                            prevGetter();
                        }
                        return handler.getter();
                    },
                    set(a) {
                        if ( prevSetter !== undefined ) {
                            prevSetter(a);
                        }
                        handler.setter(a);
                    }
                });
                safe.uboLog(logPrefix, 'Trap installed');
            } catch(ex) {
                safe.uboErr(logPrefix, ex);
            }
        };
        const trapChain = function(owner, chain) {
            const pos = chain.indexOf('.');
            if ( pos === -1 ) {
                trapProp(owner, chain, false, {
                    v: undefined,
                    init: function(v) {
                        if ( mustAbort(v) ) { return false; }
                        this.v = v;
                        return true;
                    },
                    getter: function() {
                        if ( document.currentScript === thisScript ) {
                            return this.v;
                        }
                        safe.uboLog(logPrefix, 'Property read');
                        return normalValue;
                    },
                    setter: function(a) {
                        if ( mustAbort(a) === false ) { return; }
                        normalValue = a;
                    }
                });
                return;
            }
            const prop = chain.slice(0, pos);
            const v = owner[prop];
            chain = chain.slice(pos + 1);
            if ( v instanceof safe.Object || typeof v === 'object' && v !== null ) {
                trapChain(v, chain);
                return;
            }
            trapProp(owner, prop, true, {
                v: undefined,
                init: function(v) {
                    this.v = v;
                    return true;
                },
                getter: function() {
                    return this.v;
                },
                setter: function(a) {
                    this.v = a;
                    if ( a instanceof safe.Object ) {
                        trapChain(a, chain);
                    }
                }
            });
        };
        trapChain(window, chain);
    }
    runAt(( ) => {
        setConstant(chain, rawValue);
    }, extraArgs.runAt);
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

function validateConstantFn(trusted, raw, extraArgs = {}) {
    const safe = safeSelf();
    let value;
    if ( raw === 'undefined' ) {
        value = undefined;
    } else if ( raw === 'false' ) {
        value = false;
    } else if ( raw === 'true' ) {
        value = true;
    } else if ( raw === 'null' ) {
        value = null;
    } else if ( raw === "''" || raw === '' ) {
        value = '';
    } else if ( raw === '[]' || raw === 'emptyArr' ) {
        value = [];
    } else if ( raw === '{}' || raw === 'emptyObj' ) {
        value = {};
    } else if ( raw === 'noopFunc' ) {
        value = function(){};
    } else if ( raw === 'trueFunc' ) {
        value = function(){ return true; };
    } else if ( raw === 'falseFunc' ) {
        value = function(){ return false; };
    } else if ( raw === 'throwFunc' ) {
        value = function(){ throw ''; };
    } else if ( /^-?\d+$/.test(raw) ) {
        value = parseInt(raw);
        if ( isNaN(raw) ) { return; }
        if ( Math.abs(raw) > 0x7FFF ) { return; }
    } else if ( trusted ) {
        if ( raw.startsWith('json:') ) {
            try { value = safe.JSON_parse(raw.slice(5)); } catch { return; }
        } else if ( raw.startsWith('{') && raw.endsWith('}') ) {
            try { value = safe.JSON_parse(raw).value; } catch { return; }
        }
    } else {
        return;
    }
    if ( extraArgs.as !== undefined ) {
        if ( extraArgs.as === 'function' ) {
            return ( ) => value;
        } else if ( extraArgs.as === 'callback' ) {
            return ( ) => (( ) => value);
        } else if ( extraArgs.as === 'resolved' ) {
            return Promise.resolve(value);
        } else if ( extraArgs.as === 'rejected' ) {
            return Promise.reject(value);
        }
    }
    return value;
}

/******************************************************************************/

const scriptletGlobals = {}; // eslint-disable-line
const argsList = [["console.clear","undefined"],["aclib.runInPagePush","{}","as","callback"],["aclib.runAutoTag","noopFunc"],["adBlockDetected","undefined"],["akamaiDisableServerIpLookup","noopFunc"],["DD_RUM.addAction","noopFunc"],["nads.createAd","trueFunc"],["dvtag.getTargeting","trueFunc"],["ga","noopFunc"],["huecosPBS.nstdX","null"],["DTM.trackAsyncPV","noopFunc"],["_satellite","{}"],["_satellite.getVisitorId","noopFunc"],["newPageViewSpeedtest","noopFunc"],["pubg.unload","noopFunc"],["generateGalleryAd","noopFunc"],["mediator","noopFunc"],["Object.prototype.subscribe","noopFunc"],["gbTracker","{}"],["gbTracker.sendAutoSearchEvent","noopFunc"],["Object.prototype.vjsPlayer.ads","noopFunc"],["network_user_id",""],["google.ima.OmidVerificationVendor","{}"],["Object.prototype.omidAccessModeRules","{}"],["googletag.cmd","{}"],["_aps","{}"],["Object.prototype.setDisableFlashAds","noopFunc"],["DD_RUM.addTiming","noopFunc"],["chameleonVideo.adDisabledRequested","true"],["AdmostClient","{}"],["analytics","{}"],["datalayer","[]"],["Object.prototype.isInitialLoadDisabled","noopFunc"],["listingGoogleEETracking","noopFunc"],["dcsMultiTrack","noopFunc"],["urlStrArray","noopFunc"],["pa","{}"],["Object.prototype.setConfigurations","noopFunc"],["Object.prototype.bk_addPageCtx","noopFunc"],["Object.prototype.bk_doJSTag","noopFunc"],["passFingerPrint","noopFunc"],["optimizely","{}"],["optimizely.initialized","true"],["google_optimize","{}"],["google_optimize.get","noopFunc"],["_gsq","{}"],["_gsq.push","noopFunc"],["stmCustomEvent","noopFunc"],["_gsDevice",""],["iom","{}"],["iom.c","noopFunc"],["_conv_q","{}"],["_conv_q.push","noopFunc"],["google.ima.settings.setDisableFlashAds","noopFunc"],["pa.privacy","{}"],["populateClientData4RBA","noopFunc"],["YT.ImaManager","noopFunc"],["UOLPD","{}"],["UOLPD.dataLayer","{}"],["__configuredDFPTags","{}"],["URL_VAST_YOUTUBE","{}"],["Adman","{}"],["dplus","{}"],["dplus.track","noopFunc"],["_satellite.track","noopFunc"],["google.ima.dai","{}"],["gfkS2sExtension","{}"],["gfkS2sExtension.HTML5VODExtension","noopFunc"],["AnalyticsEventTrackingJS","{}"],["AnalyticsEventTrackingJS.addToBasket","noopFunc"],["AnalyticsEventTrackingJS.trackErrorMessage","noopFunc"],["initializeslideshow","noopFunc"],["fathom","{}"],["fathom.trackGoal","noopFunc"],["Origami","{}"],["Origami.fastclick","noopFunc"],["jad","undefined"],["hasAdblocker","true"],["Sentry","{}"],["Sentry.init","noopFunc"],["TRC","{}"],["TRC._taboolaClone","[]"],["fp","{}"],["fp.t","noopFunc"],["fp.s","noopFunc"],["initializeNewRelic","noopFunc"],["turnerAnalyticsObj","{}"],["turnerAnalyticsObj.setVideoObject4AnalyticsProperty","noopFunc"],["optimizelyDatafile","{}"],["optimizelyDatafile.featureFlags","[]"],["fingerprint","{}"],["fingerprint.getCookie","noopFunc"],["gform.utils","noopFunc"],["gform.utils.trigger","noopFunc"],["get_fingerprint","noopFunc"],["moatPrebidApi","{}"],["moatPrebidApi.getMoatTargetingForPage","noopFunc"],["cpd_configdata","{}"],["cpd_configdata.url",""],["yieldlove_cmd","{}"],["yieldlove_cmd.push","noopFunc"],["dataLayer.push","noopFunc"],["_etmc","{}"],["_etmc.push","noopFunc"],["freshpaint","{}"],["freshpaint.track","noopFunc"],["ShowRewards","noopFunc"],["stLight","{}"],["stLight.options","noopFunc"],["DD_RUM.addError","noopFunc"],["sensorsDataAnalytic201505","{}"],["sensorsDataAnalytic201505.init","noopFunc"],["sensorsDataAnalytic201505.quick","noopFunc"],["sensorsDataAnalytic201505.track","noopFunc"],["s","{}"],["s.tl","noopFunc"],["smartech","noopFunc"],["sensors","{}"],["sensors.init","noopFunc"],["sensors.track","noopFunc"],["adn","{}"],["adn.clearDivs","noopFunc"],["_vwo_code","{}"],["gtag","noopFunc"],["_taboola","{}"],["_taboola.push","noopFunc"],["clicky","{}"],["clicky.goal","noopFunc"],["WURFL","{}"],["_sp_.config.events.onSPPMObjectReady","noopFunc"],["gtm","{}"],["gtm.trackEvent","noopFunc"],["mParticle.Identity.getCurrentUser","noopFunc"],["JSGlobals.prebidEnabled","false"],["elasticApm","{}"],["elasticApm.init","noopFunc"],["ga.sendGaEvent","noopFunc"],["adobe","{}"],["MT","{}"],["MT.track","noopFunc"],["ClickOmniPartner","noopFunc"],["adex","{}"],["adex.getAdexUser","noopFunc"],["Adkit","noopFunc"],["Object.prototype.shouldExpectGoogleCMP","false"],["apntag.refresh","noopFunc"],["pa.sendEvent","noopFunc"],["Munchkin","{}"],["Munchkin.init","noopFunc"],["ttd_dom_ready","noopFunc"],["ramp","undefined"],["appInfo.snowplow.trackSelfDescribingEvent","noopFunc"],["_vwo_code.init","noopFunc"],["adobePageView","noopFunc"],["dapTracker","{}"],["dapTracker.track","noopFunc"],["newrelic","{}"],["newrelic.setCustomAttribute","noopFunc"],["adobeDataLayer","{}"],["adobeDataLayer.push","noopFunc"],["Object.prototype._adsDisabled","true"],["utag","{}"],["utag.link","noopFunc"],["_satellite.kpCustomEvent","noopFunc"],["Object.prototype.disablecommercials","true"],["Object.prototype._autoPlayOnlyWithPrerollAd","false"],["Sentry.addBreadcrumb","noopFunc"],["ytInitialPlayerResponse.playerAds","undefined"],["ytInitialPlayerResponse.adPlacements","undefined"],["ytInitialPlayerResponse.adSlots","undefined"],["playerResponse.adPlacements","undefined"],["nsShowMaxCount","0"],["objVc.interstitial_web",""],["_ml_ads_ns","null"],["_sp_.config","undefined"],["AdController","noopFunc"],["console.clear","noopFunc"],["Object.prototype.hideAds","true"],["Object.prototype._getSalesHouseConfigurations","noopFunc"],["vast_urls","{}"],["sadbl","false"],["adblockcheck","false"],["arrvast","[]"],["blurred","false"],["flashvars.adv_pre_src",""],["showPopunder","false"],["page_params.holiday_promo","true"],["adsEnabled","true"],["String.prototype.charAt","trueFunc"],["ad_blocker","false"],["blockAdBlock","true"],["VikiPlayer.prototype.pingAbFactor","noopFunc"],["player.options.disableAds","true"],["console.clear","trueFunc"],["flashvars.adv_pre_vast",""],["flashvars.adv_pre_vast_alt",""],["x_width","1"],["_site_ads_ns","true"],["luxuretv.config",""],["Object.prototype.AdOverlay","noopFunc"],["tkn_popunder","null"],["can_run_ads","true"],["adsBlockerDetector","noopFunc"],["globalThis","null"],["adblock","false"],["__ads","true"],["FlixPop.isPopGloballyEnabled","falseFunc"],["check_adblock","true"],["isAdBlockActive","false"],["$.magnificPopup.open","noopFunc"],["adsenseadBlock","noopFunc"],["adblockSuspected","false"],["xRds","true"],["cRAds","false"],["disasterpingu","false"],["App.views.adsView.adblock","false"],["flashvars.adv_pause_html",""],["$.fx.off","true"],["adBlockEnabled","false"],["puShown","true"],["showAds","true"],["attr","{}"],["scriptSrc",""],["cxStartDetectionProcess","noopFunc"],["isAdBlocked","false"],["adblock","noopFunc"],["path",""],["__NEXT_DATA__.props.clientConfigSettings.videoAds","undefined"],["_ctrl_vt.blocked.ad_script","false"],["blockAdBlock","noopFunc"],["caca","noopFunc"],["Ok","true"],["safelink.adblock","false"],["openPopunder","noopFunc"],["ClickUnder","noopFunc"],["flashvars.adv_pre_url",""],["flashvars.protect_block",""],["flashvars.video_click_url",""],["adBlock","false"],["spoof","noopFunc"],["btoa","null"],["sp_ad","true"],["adsBlocked","false"],["_sp_.msg.displayMessage","noopFunc"],["CaptchmeState.adb","undefined"],["UhasAB","false"],["adNotificationDetected","false"],["atob","noopFunc"],["_pop","noopFunc"],["CnnXt.Event.fire","noopFunc"],["_ti_update_user","noopFunc"],["valid","1"],["vastAds","[]"],["adblock","1"],["frg","1"],["time","0"],["ads","true"],["GNCA_Ad_Support","true"],["Date.now","noopFunc"],["jQuery.adblock","1"],["VMG.Components.Adblock","false"],["adblockDetector","trueFunc"],["hasPoped","true"],["flashvars.video_click_url","undefined"],["flashvars.adv_start_html",""],["flashvars.popunder_url",""],["flashvars.adv_post_src",""],["flashvars.adv_post_url",""],["jQuery.adblock","false"],["google_jobrunner","true"],["sec","0"],["gadb","false"],["checkadBlock","noopFunc"],["clientSide.adbDetect","noopFunc"],["HTMLAnchorElement.prototype.click","noopFunc"],["cmnnrunads","true"],["adBlocker","false"],["adBlockDetected","noopFunc"],["StileApp.somecontrols.adBlockDetected","noopFunc"],["google_tag_data","noopFunc"],["noAdBlock","true"],["adsOk","true"],["check","true"],["isal","true"],["document.hidden","true"],["awm","true"],["adblockEnabled","false"],["is_adblocked","false"],["pogo.intermission.staticAdIntermissionPeriod","0"],["SubmitDownload1","noopFunc"],["t","0"],["ckaduMobilePop","noopFunc"],["tieneAdblock","0"],["adsAreBlocked","false"],["cmgpbjs","false"],["displayAdblockOverlay","false"],["google","false"],["Math.pow","noopFunc"],["openInNewTab","noopFunc"],["runAdBlocker","false"],["Adblock","false"],["flashvars.logo_url",""],["flashvars.logo_text",""],["nlf.custom.userCapabilities","false"],["count","0"],["LoadThisScript","true"],["showPremLite","true"],["closeBlockerModal","false"],["adBlockDetector.isEnabled","falseFunc"],["areAdsDisplayed","true"],["gkAdsWerbung","true"],["pop_target","null"],["is_banner","true"],["$easyadvtblock","false"],["show_dfp_preroll","false"],["show_youtube_preroll","false"],["doads","true"],["jsUnda","noopFunc"],["AlobaidiDetectAdBlock","true"],["Advertisement","1"],["adBlockDetected","false"],["abp1","1"],["pr_okvalida","true"],["$.ajax","trueFunc"],["cnbc.canShowAds","true"],["firefaucet","true"],["cRAds","true"],["uas","[]"],["flashvars.popunder_url","undefined"],["adv","true"],["prerollMain","undefined"],["canRunAds","true"],["Fingerprint2","true"],["dclm_ajax_var.disclaimer_redirect_url",""],["load_pop_power","noopFunc"],["adBlockDetected","true"],["Time_Start","0"],["blockAdBlock","trueFunc"],["ezstandalone.enabled","true"],["foundation.adPlayer.bitmovin","{}"],["weltConfig.switches.videoAdBlockBlocker","false"],["DL8_GLOBALS.enableAdSupport","false"],["DL8_GLOBALS.useHomad","false"],["DL8_GLOBALS.enableHomadDesktop","false"],["DL8_GLOBALS.enableHomadMobile","false"],["Object.prototype.adReinsertion","noopFunc"],["getHomadConfig","noopFunc"],["ab","false"],["go_popup","{}"],["noBlocker","true"],["adsbygoogle","null"],["fabActive","false"],["gWkbAdVert","true"],["noblock","true"],["wgAffiliateEnabled","false"],["ads","null"],["detectAdblock","noopFunc"],["adsLoadable","true"],["ASSetCookieAds","null"],["letShowAds","true"],["ulp_noadb","true"],["Object.prototype.adblock_detected","false"],["timeSec","0"],["adsbygoogle.loaded","true"],["ads_unblocked","true"],["xxSetting.adBlockerDetection","false"],["open","undefined"],["Drupal.behaviors.adBlockerPopup","null"],["fake_ad","true"],["koddostu_com_adblock_yok","null"],["adsbygoogle","trueFunc"],["player.ads.cuePoints","undefined"],["adBlockDetected","null"],["better_ads_adblock","1"],["Adv_ab","false"],["sgpbCanRunAds","true"],["document.hidden","false"],["hasFocus","trueFunc"],["navigator.brave","undefined"],["Object.prototype.isAllAdClose","true"],["document.hasFocus","trueFunc"],["isRequestPresent","true"],["fouty","true"],["Notification","undefined"],["protection","noopFunc"],["private","false"],["navigator.webkitTemporaryStorage.queryUsageAndQuota","noopFunc"],["document.onkeydown","noopFunc"],["showadas","true"],["alert","throwFunc"],["aSl.gcd","0"],["window.adLink","null"],["detectedAdblock","undefined"],["isTabActive","true"],["clicked","2"],["ov.advertising.tisoomi.loadScript","noopFunc"],["abp","false"],["hommy","{}"],["hommy.waitUntil","noopFunc"],["flashvars.mlogo",""],["vpPrerollVideo","undefined"],["PlayerConfig.config.CustomAdSetting","[]"],["PlayerConfig.trusted","true"],["PlayerConfig.config.AffiliateAdViewLevel","3"],["univresalP","noopFunc"],["hold_click","false"],["tie.ad_blocker_detector","false"],["admiral","noopFunc"],["gnt.x.uam"],["gnt.u.z","true"],["__INITIAL_DATA__.siteData.admiralScript"],["objAd.loadAdShield","noopFunc"],["window.myAd.runAd","noopFunc"],["detectAdBlock","noopFunc"],["AHE.is_member","1"],["__INITIAL_STATE__.config.theme.ads.isAdBlockerEnabled","false"],["__INITIAL_STATE__.gameLists.gamesNoPrerollIds.indexOf","trueFunc"],["document.ontouchend","null"],["document.onclick","null"],["playID","1"],["MDCore.adblock","0"],["killads","true"],["NMAFMediaPlayerController.vastManager.vastShown","true"],["__NEXT_DATA__.runtimeConfig._qub_sdk.qubConfig.video.adBlockerDetectorEnabled","false"],["arePiratesOnBoard","false"],["googletag._loaded_","true"],["NoTenia","false"],["app._data.ads","[]"],["adsPlayer","undefined"],["pubAdsService","trueFunc"],["config.pauseInspect","false"],["appContext.adManager.context.current.adFriendly","false"],["blockAdBlock._options.baitClass","null"],["document.blocked_var","1"],["____ads_js_blocked","false"],["wIsAdBlocked","false"],["WebSite.plsDisableAdBlock","null"],["ads_blocked","false"],["samDetected","false"],["countClicks","0"],["settings.adBlockerDetection","false"],["mixpanel.get_distinct_id","true"],["fuckAdBlock._options.baitClass","null"],["bscheck.adblocker","noopFunc"],["qpcheck.ads","noopFunc"],["isContentBlocked","falseFunc"],["CloudflareApps.installs.Ik7rmQ4t95Qk.options.measureDomain","undefined"],["detectAB1","noopFunc"],["uBlockOriginDetected","false"],["googletag._vars_","{}"],["googletag._loadStarted_","true"],["google_unique_id","1"],["google.javascript","{}"],["google.javascript.ads","{}"],["google_global_correlator","1"],["paywallGateway.truncateContent","noopFunc"],["adBlockDisabled","true"],["__NEXT_DATA__.props.pageProps.adVideo","undefined"],["blockedElement","noopFunc"],["popit","false"],["adBlockerDetected","false"],["abu","falseFunc"],["countdown","0"],["decodeURI","noopFunc"],["flashvars.adv_postpause_vast",""],["xv_ad_block","0"],["openWindow","noopFunc"],["vidorev_jav_plugin_video_ads_object.vid_ads_m_video_ads",""],["adsProvider.init","noopFunc"],["SDKLoaded","true"],["POPUNDER_ENABLED","false"],["plugins.preroll","noopFunc"],["errcode","0"],["DHAntiAdBlocker","true"],["showada","true"],["showax","true"],["p18","undefined"],["ADBLOCKED","false"],["Object.prototype.adsEnabled","false"],["adb","0"],["String.fromCharCode","trueFunc"],["adblock_use","false"],["Object.prototype.adblockFound","false"],["createCanvas","noopFunc"],["document.bridCanRunAds","true"],["playerAdSettings.adLink",""],["playerAdSettings.waitTime","0"],["xv.sda.pp.init","noopFunc"],["isAdsLoaded","true"],["adblockerAlert","noopFunc"],["Object.prototype.parseXML","noopFunc"],["Object.prototype.blackscreenDuration","1"],["Object.prototype.adPlayerId",""],["adblockDetect","noopFunc"],["style","noopFunc"],["history.pushState","noopFunc"],["google_unique_id","6"],["__NEXT_DATA__.props.pageProps.adsConfig","undefined"],["new_config.timedown","0"],["truex","{}"],["truex.client","noopFunc"],["hiddenProxyDetected","false"],["SteadyWidgetSettings.adblockActive","false"],["proclayer","noopFunc"],["timeleft","0"],["load_ads","trueFunc"],["starPop","1"],["Object.prototype.ads","noopFunc"],["detectBlockAds","noopFunc"],["ad_link",""],["penciBlocksArray","[]"],["App.AdblockDetected","false"],["SF.adblock","true"],["startfrom","0"],["D4zz","noopFunc"],["Object.prototype.ads.nopreroll_","true"],["HP_Scout.adBlocked","false"],["SD_IS_BLOCKING","false"],["Object.prototype.isPremium","true"],["__BACKPLANE_API__.renderOptions.showAdBlock",""],["Object.prototype.isNoAds","{}"],["tv3Cmp.ConsentGiven","true"],["setupSkin","noopFunc"],["Object.prototype.enableInterstitial","false"],["ads","undefined"],["td_ad_background_click_link","undefined"],["POSTPART_prototype.ADKEY","noopFunc"],["adBlockDetected","falseFunc"],["divWidth","1"],["noAdBlock","noopFunc"],["AdService.info.abd","noopFunc"],["adBlockDetectionResult","undefined"],["popped","true"],["puShown1","true"],["passthetest","true"],["pandaAdviewValidate","true"],["canGetAds","true"],["ad_blocker_active","false"],["init_welcome_ad","noopFunc"],["document.body.contains","trueFunc"],["popunder","undefined"],["distance","0"],["document.onclick",""],["adEnable","true"],["displayAds","0"],["_adshrink.skiptime","0"],["AbleToRunAds","true"],["PreRollAd.timeCounter","0"],["abpblocked","undefined"],["paAddUnit","noopFunc"],["adt","0"],["test_adblock","noopFunc"],["adblockDetector","noopFunc"],["vastEnabled","false"],["detectadsbocker","false"],["two_worker_data_js.js","[]"],["FEATURE_DISABLE_ADOBE_POPUP_BY_COUNTRY","true"],["questpassGuard","noopFunc"],["isAdBlockerEnabled","false"],["sssp","emptyObj"],["smartLoaded","true"],["timeLeft","0"],["Cookiebot","noopFunc"],["feature_flags.interstitial_ads_flag","false"],["feature_flags.interstitials_every_four_slides","false"],["waldoSlotIds","true"],["adblockstatus","false"],["adScriptLoaded","true"],["adblockEnabled","noopFunc"],["adSettings","[]"],["banner_is_blocked","false"],["Object.prototype.adBlocked","false"],["chp_adblock_browser","noopFunc"],["googleAd","true"],["Brid.A9.prototype.backfillAdUnits","[]"],["dct","0"],["slideShow.displayInterstitial","true"],["googletag","true"],["tOS2","150"],["checkAdBlocker","noopFunc"],["navigator.standalone","true"],["empire.pop","undefined"],["empire.direct","undefined"],["empire.directHideAds","undefined"],["empire.mediaData.advisorMovie","1"],["empire.mediaData.advisorSerie","1"],["setTimer","0"],["penci_adlbock.ad_blocker_detector","0"],["Object.prototype.adblockDetector","noopFunc"],["blext","true"],["vidorev_jav_plugin_video_ads_object","{}"],["vidorev_jav_plugin_video_ads_object_post","{}"],["S_Popup","10"],["rabLimit","-1"],["nudgeAdBlock","noopFunc"],["feedBack.showAffilaePromo","noopFunc"],["ShowAdvertising","{}"],["FAVE.settings.ads.ssai.prod.clips.enabled","false"],["FAVE.settings.ads.ssai.prod.liveAuth.enabled","false"],["FAVE.settings.ads.ssai.prod.liveUnauth.enabled","false"],["HTMLScriptElement.prototype.onerror","null"],["loadpagecheck","noopFunc"],["art3m1sItemNames.affiliate-wrapper","\"\""],["isAdBlockerActive","noopFunc"],["di.app.WebplayerApp.Ads.Adblocks.app.AdBlockDetectApp.startWithParent","false"],["sharedController.adblockDetector","noopFunc"],["checkAdsStatus","noopFunc"],["settings.adBlockDetectionEnabled","false"],["displayInterstitialAdConfig","false"],["checkAdBlockeraz","noopFunc"],["blockingAds","false"],["Yii2App.playbackTimeout","0"],["QiyiPlayerProphetData.a.data","{}"],["toggleAdBlockInfo","falseFunc"],["aipAPItag.prerollSkipped","true"],["aipAPItag.setPreRollStatus","trueFunc"],["reklam_1_saniye","0"],["reklam_1_gecsaniye","0"],["reklamsayisi","1"],["reklam_1",""],["HTMLImageElement.prototype.onerror","undefined"],["HTMLImageElement.prototype.onload","undefined"],["powerAPITag","emptyObj"],["playerEnhancedConfig.run","throwFunc"],["aoAdBlockDetected","false"],["rodo.checkIsDidomiConsent","noopFunc"],["xtime","0"],["Div_popup",""],["Scribd.Blob.AdBlockerModal","noopFunc"],["AddAdsV2I.addBlock","false"],["hasAdBlocker","false"],["initials.yld-pdpopunder",""],["advertisement3","true"],["Object.prototype.skipPreroll","true"],["DisableDevtool","noopFunc"],["clicked","true"],["eClicked","true"],["number","0"],["sync","true"],["PlayerLogic.prototype.detectADB","noopFunc"],["showPopunder","noopFunc"],["Object.prototype.prerollAds","[]"],["notifyMe","noopFunc"],["adsClasses","undefined"],["gsecs","0"],["dvsize","52"],["majorse","true"],["completed","1"],["testerli","false"],["w87.abd","noopFunc"],["w87.dsab","noopFunc"],["document.referrer",""],["Object.prototype.setNeedShowAdblockWarning","noopFunc"],["NoAdBlock","noopFunc"],["adList","[]"],["ifmax","true"],["nitroAds.abp","true"],["onloadUI","noopFunc"],["PageLoader.DetectAb","0"],["one_time","1"],["consentGiven","true"],["GEMG.GPT.Interstitial","noopFunc"],["amiblock","0"],["karte3","18"],["sandDetect","noopFunc"],["amodule.data","emptyArr"],["Object.prototype.ADBLOCK_DETECTION",""],["postroll","undefined"],["interstitial","undefined"],["isAdBlockDetected","false"],["pData.adblockOverlayEnabled","0"],["cabdSettings","undefined"],["td_ad_background_click_link"],["malisx","true"],["alim","true"],["ADS.isBannersEnabled","false"],["EASYFUN_ADS_CAN_RUN","true"],["adsbygoogle_ama_fc_has_run","true"],["jwDefaults.advertising","{}"],["elimina_profilazione","1"],["elimina_pubblicita","1"],["abd","{}"],["checkerimg","noopFunc"],["detectedAdblock","noopFunc"],["Object.prototype.DetectByGoogleAd","noopFunc"],["nitroAds","{}"],["nitroAds.createAd","noopFunc"],["NativeAd","noopFunc"],["window.navigator.brave","undefined"],["HTMLScriptElement.prototype.onerror","undefined"],["isAdblock","false"],["openPop","noopFunc"],["cns.library","true"],["BJSShowUnder","{}"],["BJSShowUnder.bindTo","noopFunc"],["BJSShowUnder.add","noopFunc"],["Object.prototype._parseVAST","noopFunc"],["Object.prototype.createAdBlocker","noopFunc"],["Object.prototype.isAdPeriod","falseFunc"],["ABLK","false"],["_n_app.popunder","null"],["_n_app.options.ads.show_popunders","false"],["N_BetterJsPop.object","{}"],["isAdb","false"],["puOverlay","noopFunc"],["ue_adb_chk","1"],["countDown","0"],["runCheck","noopFunc"],["adsSlotRenderEndSeen","true"],["showModal","noopFunc"],["flashvars.mlogo_link",""],["isAdBlocked","noopFunc"],["URLlist","[]"],["aaw","{}"],["aaw.processAdsOnPage","noopFunc"],["doOpen","undefined"],["OneTrust","{}"],["OneTrust.IsAlertBoxClosed","trueFunc"],["FOXIZ_MAIN_SCRIPT.siteAccessDetector","noopFunc"],["openAdBlockPopup","noopFunc"],["advanced_ads_check_adblocker","noopFunc"],["canRunAds","1"],["attestHasAdBlockerActivated","true"],["extInstalled","true"],["SaveFiles.add","noopFunc"],["detectSandbox","noopFunc"],["ga","trueFunc"],["adbon","0"],["LCI.adBlockDetectorEnabled","false"],["stoCazzo","true"],["adblockDetected","false"],["importFAB","undefined"],["window.__CONFIGURATION__.adInsertion.enabled","false"],["window.__CONFIGURATION__.features.enableAdBlockerDetection","false"],["_carbonads","{}"],["_bsa","{}"],["uberad_mode"],["__aab_init","true"],["show_videoad_limited","noopFunc"],["__NATIVEADS_CANARY__","true"],["docManager.doDynamicBlurring","noopFunc"],["Object.prototype.adOnAdBlockPreventPlayback","false"],["pre_roll_url"],["post_roll_url"],["player.preroll","noopFunc"],["rwt","noopFunc"],["bmak.js_post","false"],["firebase.analytics","noopFunc"],["Object.prototype.updateModifiedCommerceUrl","noopFunc"],["flashvars.event_reporting",""],["Object.prototype.has_opted_out_tracking","trueFunc"],["process","{}"],["process.env","{}"],["Visitor","{}"],["send_gravity_event","noopFunc"],["send_recommendation_event","noopFunc"],["libAnalytics.data.get","noopFunc"],["adthrive._components.start","noopFunc"],["data","true"],["navigator.sendBeacon","noopFunc"]];
const hostnamesMap = new Map([["jilliandescribecompany.com",0],["gogoanime.*",[0,207]],["adrianmissionminute.com",0],["alejandrocenturyoil.com",0],["alleneconomicmatter.com",0],["bethshouldercan.com",0],["bigclatterhomesguideservice.com",0],["brittneystandardwestern.com",0],["brookethoughi.com",0],["brucevotewithin.com",0],["cindyeyefinal.com",0],["denisegrowthwide.com",0],["diananatureforeign.com",0],["donaldlineelse.com",0],["edwardarriveoften.com",0],["erikcoldperson.com",0],["evelynthankregion.com",0],["graceaddresscommunity.com",0],["heatherdiscussionwhen.com",0],["heatherwholeinvolve.com",0],["housecardsummerbutton.com",0],["jamessoundcost.com",0],["jamiesamewalk.com",0],["jasminetesttry.com",0],["jasonresponsemeasure.com",0],["jayservicestuff.com",0],["jennifercertaindevelopment.com",0],["jessicaglassauthor.com",0],["johnalwayssame.com",0],["johntryopen.com",0],["jonathansociallike.com",0],["josephseveralconcern.com",0],["kellywhatcould.com",0],["kennethofficialitem.com",0],["kristiesoundsimply.com",0],["lisatrialidea.com",0],["lorimuchbenefit.com",0],["loriwithinfamily.com",0],["lukecomparetwo.com",0],["lukesitturn.com",0],["mariatheserepublican.com",0],["markstyleall.com",0],["michaelapplysome.com",0],["morganoperationface.com",0],["nathanfromsubject.com",0],["paulkitchendark.com",0],["rebeccaneverbase.com",0],["richardsignfish.com",0],["roberteachfinal.com",0],["robertordercharacter.com",0],["robertplacespace.com",0],["ryanagoinvolve.com",0],["sandratableother.com",0],["sandrataxeight.com",0],["sethniceletter.com",0],["shannonpersonalcost.com",0],["susanhavekeep.com",0],["tinycat-voe-fashion.com",0],["toddpartneranimal.com",0],["troyyourlead.com",0],["uptodatefinishconference.com",0],["uptodatefinishconferenceroom.com",0],["voe.sx",0],["maxfinishseveral.com",0],["voe.sx>>",0],["javboys.tv>>",0],["freeplayervideo.com",0],["nazarickol.com",0],["player-cdn.com",0],["playhydrax.com",[0,417,418]],["rabbitstream.net",0],["fmovies.*",0],["japscan.*",[1,2]],["u26bekrb.fun",3],["br.de",4],["indeed.com",5],["zillow.com",[5,109]],["pasteboard.co",6],["bbc.com",7],["clickhole.com",8],["deadspin.com",8],["gizmodo.com",8],["jalopnik.com",8],["jezebel.com",8],["kotaku.com",8],["lifehacker.com",8],["splinternews.com",8],["theinventory.com",8],["theonion.com",8],["theroot.com",8],["thetakeout.com",8],["pewresearch.org",8],["los40.com",[9,10]],["as.com",10],["caracol.com.co",10],["telegraph.co.uk",[11,12]],["poweredbycovermore.com",[11,64]],["lumens.com",[11,64]],["verizon.com",13],["humanbenchmark.com",14],["politico.com",15],["officedepot.co.cr",[16,17]],["officedepot.*",[18,19]],["usnews.com",20],["coolmathgames.com",[21,294,295,296]],["video.gazzetta.it",[22,23]],["oggi.it",[22,23]],["manoramamax.com",22],["factable.com",24],["thedailybeast.com",25],["zee5.com",26],["gala.fr",27],["geo.fr",27],["voici.fr",27],["gloucestershirelive.co.uk",28],["arsiv.mackolik.com",29],["jacksonguitars.com",30],["scandichotels.com",31],["stylist.co.uk",32],["nettiauto.com",33],["thaiairways.com",[34,35]],["cerbahealthcare.it",[36,37]],["futura-sciences.com",[36,54]],["toureiffel.paris",36],["campusfrance.org",[36,146]],["tiendaenlinea.claro.com.ni",[38,39]],["tieba.baidu.com",40],["fandom.com",[41,42,354]],["grasshopper.com",[43,44]],["epson.com.cn",[45,46,47,48]],["oe24.at",[49,50]],["szbz.de",49],["platform.autods.com",[51,52]],["kcra.com",53],["wcvb.com",53],["sporteurope.tv",53],["citibank.com.sg",55],["uol.com.br",[56,57,58,59,60]],["gazzetta.gr",61],["digicol.dpm.org.cn",[62,63]],["virginmediatelevision.ie",65],["larazon.es",[66,67]],["waitrosecellar.com",[68,69,70]],["kicker.de",[71,395]],["sharpen-free-design-generator.netlify.app",[72,73]],["help.cashctrl.com",[74,75]],["gry-online.pl",76],["vidaextra.com",77],["commande.rhinov.pro",[78,79]],["ecom.wixapps.net",[78,79]],["prod.hydra.sophos.com",[78,166]],["tipranks.com",[80,81]],["iceland.co.uk",[82,83,84]],["socket.pearsoned.com",85],["tntdrama.com",[86,87]],["trutv.com",[86,87]],["mobile.de",[88,89]],["ioe.vn",[90,91]],["geiriadur.ac.uk",[90,94]],["welsh-dictionary.ac.uk",[90,94]],["bikeportland.org",[92,93]],["biologianet.com",[57,58,59]],["10.com.au",[95,96]],["10play.com.au",[95,96]],["sunshine-live.de",[97,98]],["whatismyip.com",[99,100]],["myfitnesspal.com",101],["netoff.co.jp",[102,103]],["bluerabbitrx.com",[102,103]],["foundit.*",[104,105]],["clickjogos.com.br",106],["bristan.com",[107,108]],["share.hntv.tv",[110,111,112,113]],["forum.dji.com",[110,113]],["unionpayintl.com",[110,112]],["streamelements.com",110],["optimum.net",[114,115]],["hdfcfund.com",116],["user.guancha.cn",[117,118]],["sosovalue.com",119],["bandyforbundet.no",[120,121]],["tatacommunications.com",122],["kb.arlo.com",[122,152]],["suamusica.com.br",[123,124,125]],["macrotrends.net",[126,127]],["code.world",128],["smartcharts.net",128],["topgear.com",129],["eservice.directauto.com",[130,131]],["nbcsports.com",132],["standard.co.uk",133],["pruefernavi.de",[134,135]],["17track.net",136],["visible.com",137],["hagerty.com",[138,139]],["marketplace.nvidia.com",140],["kino.de",[141,142]],["9now.nine.com.au",143],["worldstar.com",144],["prisjakt.no",145],["developer.arm.com",[147,148]],["sterkinekor.com",149],["iogames.space",150],["id.condenast.com",151],["tires.costco.com",153],["tires.costco.ca",153],["livemint.com",[154,155]],["login.asda.com",[156,157]],["mandai.com",[158,159]],["damndelicious.net",160],["laurelberninteriors.com",[160,757]],["brother-usa.com",[161,162]],["choose.kaiserpermanente.org",163],["tekniikanmaailma.fi",[164,165]],["m.youtube.com",[167,168,169,170]],["music.youtube.com",[167,168,169,170]],["tv.youtube.com",[167,168,169,170]],["www.youtube.com",[167,168,169,170]],["youtubekids.com",[167,168,169,170]],["youtube-nocookie.com",[167,168,169,170]],["eu-proxy.startpage.com",[167,168,170]],["timesofindia.indiatimes.com",171],["economictimes.indiatimes.com",172],["motherless.com",173],["sueddeutsche.de",174],["wiwo.de",175],["primewire.*",176],["alphaporno.com",[176,553]],["porngem.com",176],["shortit.pw",[176,251]],["familyporn.tv",176],["sbplay.*",176],["85po.com",[176,236]],["milfnut.*",176],["k1nk.co",176],["watchasians.cc",176],["sankakucomplex.com",177],["player.glomex.com",178],["merkur.de",178],["tz.de",178],["sxyprn.*",179],["hqq.*",[180,181]],["waaw.*",[181,182]],["hotpornfile.org",181],["younetu.*",181],["multiup.us",181],["peliculas8k.com",[181,182]],["czxxx.org",181],["vtplayer.online",181],["vvtplayer.*",181],["netu.ac",181],["netu.frembed.lol",181],["123link.*",183],["adshort.*",183],["mitly.us",183],["linkrex.net",183],["linx.cc",183],["oke.io",183],["linkshorts.*",183],["dz4link.com",183],["adsrt.*",183],["linclik.com",183],["shrt10.com",183],["vinaurl.*",183],["loptelink.com",183],["adfloz.*",183],["cut-fly.com",183],["linkfinal.com",183],["payskip.org",183],["cutpaid.com",183],["linkjust.com",183],["leechpremium.link",183],["icutlink.com",[183,270]],["oncehelp.com",183],["rgl.vn",183],["reqlinks.net",183],["bitlk.com",183],["qlinks.eu",183],["link.3dmili.com",183],["short-fly.com",183],["foxseotools.com",183],["dutchycorp.*",183],["shortearn.*",183],["pingit.*",183],["link.turkdown.com",183],["7r6.com",183],["oko.sh",183],["ckk.ai",183],["fc.lc",183],["fstore.biz",183],["shrink.*",183],["cuts-url.com",183],["eio.io",183],["exe.app",183],["exee.io",183],["exey.io",183],["skincarie.com",183],["exeo.app",183],["tmearn.*",183],["coinlyhub.com",[183,332]],["adsafelink.com",183],["aii.sh",183],["megalink.*",183],["cybertechng.com",[183,348]],["cutdl.xyz",183],["iir.ai",183],["shorteet.com",[183,366]],["miniurl.*",183],["smoner.com",183],["gplinks.*",183],["odisha-remix.com",[183,348]],["xpshort.com",[183,348]],["upshrink.com",183],["clk.*",183],["easysky.in",183],["veganab.co",183],["golink.bloggerishyt.in",183],["birdurls.com",183],["vipurl.in",183],["jameeltips.us",183],["promo-visits.site",183],["satoshi-win.xyz",[183,382]],["shorterall.com",183],["encurtandourl.com",183],["forextrader.site",183],["postazap.com",183],["cety.app",183],["exego.app",[183,380]],["cutlink.net",183],["cutyurls.com",183],["cutty.app",183],["cutnet.net",183],["jixo.online",183],["tinys.click",[183,348]],["cpm.icu",183],["panyshort.link",183],["enagato.com",183],["pandaznetwork.com",183],["tpi.li",183],["oii.la",183],["recipestutorials.com",183],["shrinkme.*",183],["shrinke.*",183],["mrproblogger.com",183],["themezon.net",183],["shrinkforearn.in",183],["oii.io",183],["du-link.in",183],["atglinks.com",183],["thotpacks.xyz",183],["megaurl.in",183],["megafly.in",183],["simana.online",183],["fooak.com",183],["joktop.com",183],["evernia.site",183],["falpus.com",183],["link.paid4link.com",183],["exalink.fun",183],["shortxlinks.com",183],["upfion.com",183],["upfiles.app",183],["upfiles-urls.com",183],["flycutlink.com",[183,348]],["linksly.co",183],["link1s.*",183],["pkr.pw",183],["imagenesderopaparaperros.com",183],["shortenbuddy.com",183],["apksvip.com",183],["4cash.me",183],["namaidani.com",183],["shortzzy.*",183],["teknomuda.com",183],["shorttey.*",[183,331]],["miuiku.com",183],["savelink.site",183],["lite-link.*",183],["adcorto.*",183],["samaa-pro.com",183],["miklpro.com",183],["modapk.link",183],["ccurl.net",183],["linkpoi.me",183],["pewgame.com",183],["haonguyen.top",183],["zshort.*",183],["crazyblog.in",183],["cutearn.net",183],["rshrt.com",183],["filezipa.com",183],["dz-linkk.com",183],["upfiles.*",183],["theblissempire.com",183],["finanzas-vida.com",183],["adurly.cc",183],["paid4.link",183],["link.asiaon.top",183],["go.gets4link.com",183],["linkfly.*",183],["beingtek.com",183],["shorturl.unityassets4free.com",183],["disheye.com",183],["techymedies.com",183],["za.gl",[183,284]],["bblink.com",183],["myad.biz",183],["swzz.xyz",183],["vevioz.com",183],["charexempire.com",183],["clk.asia",183],["sturls.com",183],["myshrinker.com",183],["wplink.*",183],["rocklink.in",183],["techgeek.digital",183],["download3s.net",183],["shortx.net",183],["tlin.me",183],["bestcash2020.com",183],["adslink.pw",[183,634]],["novelssites.com",183],["faucetcrypto.net",183],["trxking.xyz",183],["weadown.com",183],["m.bloggingguidance.com",183],["link.codevn.net",183],["link4rev.site",183],["c2g.at",183],["bitcosite.com",[183,567]],["cryptosh.pro",183],["windowslite.net",[183,348]],["viewfr.com",183],["cl1ca.com",183],["4br.me",183],["fir3.net",183],["seulink.*",183],["encurtalink.*",183],["kiddyshort.com",183],["watchmygf.me",[184,209]],["camwhores.*",[184,194,235,236,237]],["camwhorez.tv",[184,194,235,236]],["cambay.tv",[184,216,235,262,264,265,266,267]],["fpo.xxx",[184,216]],["sexemix.com",184],["heavyfetish.com",[184,749]],["thotcity.su",184],["viralxxxporn.com",[184,399]],["tube8.*",[185,186]],["you-porn.com",186],["youporn.*",186],["youporngay.com",186],["youpornru.com",186],["redtube.*",186],["9908ww.com",186],["adelaidepawnbroker.com",186],["bztube.com",186],["hotovs.com",186],["insuredhome.org",186],["nudegista.com",186],["pornluck.com",186],["vidd.se",186],["pornhub.*",[186,321]],["pornhub.com",186],["pornerbros.com",187],["freep.com",187],["porn.com",188],["tune.pk",189],["noticias.gospelmais.com.br",190],["techperiod.com",190],["viki.com",[191,192]],["watch-series.*",193],["watchseries.*",193],["vev.*",193],["vidop.*",193],["vidup.*",193],["sleazyneasy.com",[194,195,196]],["smutr.com",[194,328]],["tktube.com",194],["yourporngod.com",[194,195]],["javbangers.com",[194,464]],["camfox.com",194],["camthots.tv",[194,262]],["shegotass.info",194],["amateur8.com",194],["bigtitslust.com",194],["ebony8.com",194],["freeporn8.com",194],["lesbian8.com",194],["maturetubehere.com",194],["sortporn.com",194],["motherporno.com",[194,195,216,264]],["theporngod.com",[194,195]],["watchdirty.to",[194,236,237,265]],["pornsocket.com",197],["luxuretv.com",198],["porndig.com",[199,200]],["webcheats.com.br",201],["ceesty.com",[202,203]],["gestyy.com",[202,203]],["corneey.com",203],["destyy.com",203],["festyy.com",203],["sh.st",203],["mitaku.net",203],["angrybirdsnest.com",204],["zrozz.com",204],["clix4btc.com",204],["4tests.com",204],["goltelevision.com",204],["news-und-nachrichten.de",204],["laradiobbs.net",204],["urlaubspartner.net",204],["produktion.de",204],["cinemaxxl.de",204],["bladesalvador.com",204],["tempr.email",204],["friendproject.net",204],["covrhub.com",204],["trust.zone",204],["business-standard.com",204],["planetsuzy.org",205],["empflix.com",206],["xmovies8.*",207],["masteranime.tv",207],["0123movies.*",207],["gostream.*",207],["gomovies.*",207],["freeviewmovies.com",208],["filehorse.com",208],["guidetnt.com",208],["starmusiq.*",208],["sp-today.com",208],["linkvertise.com",208],["eropaste.net",208],["getpaste.link",208],["sharetext.me",208],["wcofun.*",208],["note.sieuthuthuat.com",208],["gadgets.es",[208,473]],["amateurporn.co",[208,265]],["watchanimesub.net",208],["wcoanimesub.tv",208],["wcoforever.net",208],["transparentcalifornia.com",209],["deepbrid.com",210],["webnovel.com",211],["streamwish.*",[212,213]],["oneupload.to",213],["wishfast.top",213],["rubystm.com",213],["rubyvid.com",213],["rubyvidhub.com",213],["stmruby.com",213],["streamruby.com",213],["schwaebische.de",214],["8tracks.com",215],["3movs.com",216],["bravoerotica.net",[216,264]],["youx.xxx",216],["camclips.tv",[216,328]],["xtits.*",[216,264]],["camflow.tv",[216,264,265,302,399]],["camhoes.tv",[216,262,264,265,302,399]],["xmegadrive.com",216],["xxxymovies.com",216],["xxxshake.com",216],["gayck.com",216],["xhand.com",[216,264]],["analdin.com",[216,264]],["revealname.com",217],["golfchannel.com",218],["stream.nbcsports.com",218],["mathdf.com",218],["gamcore.com",219],["porcore.com",219],["porngames.tv",219],["69games.xxx",219],["asianpornjav.com",219],["javmix.app",219],["haaretz.co.il",220],["haaretz.com",220],["hungama.com",220],["a-o.ninja",220],["anime-odcinki.pl",220],["shortgoo.blogspot.com",220],["tonanmedia.my.id",[220,586]],["isekaipalace.com",220],["plyjam.*",[221,222]],["foxsports.com.au",223],["canberratimes.com.au",223],["thesimsresource.com",224],["fxporn69.*",225],["vipbox.*",226],["viprow.*",226],["nba.com",227],["ctrl.blog",228],["sportlife.es",229],["finofilipino.org",230],["desbloqueador.*",231],["xberuang.*",232],["teknorizen.*",232],["mysflink.blogspot.com",232],["ashemaletube.*",233],["paktech2.com",233],["assia.tv",234],["assia4.com",234],["cwtvembeds.com",[236,263]],["camlovers.tv",236],["porntn.com",236],["pornissimo.org",236],["sexcams-24.com",[236,265]],["watchporn.to",[236,265]],["camwhorez.video",236],["footstockings.com",[236,237,265]],["xmateur.com",[236,237,265]],["multi.xxx",237],["weatherx.co.in",[238,239]],["sunbtc.space",238],["subtorrents.*",240],["subtorrents1.*",240],["newpelis.*",240],["pelix.*",240],["allcalidad.*",240],["infomaniakos.*",240],["ojogos.com.br",241],["powforums.com",242],["supforums.com",242],["studybullet.com",242],["usgamer.net",243],["recordonline.com",243],["freebitcoin.win",244],["e-monsite.com",244],["coindice.win",244],["freiepresse.de",245],["investing.com",246],["tornadomovies.*",247],["mp3fiber.com",248],["chicoer.com",249],["dailybreeze.com",249],["dailybulletin.com",249],["dailynews.com",249],["delcotimes.com",249],["eastbaytimes.com",249],["macombdaily.com",249],["ocregister.com",249],["pasadenastarnews.com",249],["pe.com",249],["presstelegram.com",249],["redlandsdailyfacts.com",249],["reviewjournal.com",249],["santacruzsentinel.com",249],["saratogian.com",249],["sentinelandenterprise.com",249],["sgvtribune.com",249],["tampabay.com",249],["times-standard.com",249],["theoaklandpress.com",249],["trentonian.com",249],["twincities.com",249],["whittierdailynews.com",249],["bostonherald.com",249],["dailycamera.com",249],["sbsun.com",249],["dailydemocrat.com",249],["montereyherald.com",249],["orovillemr.com",249],["record-bee.com",249],["redbluffdailynews.com",249],["reporterherald.com",249],["thereporter.com",249],["timescall.com",249],["timesheraldonline.com",249],["ukiahdailyjournal.com",249],["dailylocal.com",249],["mercurynews.com",249],["suedkurier.de",250],["anysex.com",252],["icdrama.*",253],["mangasail.*",253],["pornve.com",254],["file4go.*",255],["coolrom.com.au",255],["marie-claire.es",256],["gamezhero.com",256],["flashgirlgames.com",256],["onlinesudoku.games",256],["mpg.football",256],["sssam.com",256],["globalnews.ca",257],["drinksmixer.com",258],["leitesculinaria.com",258],["fupa.net",259],["browardpalmbeach.com",260],["dallasobserver.com",260],["houstonpress.com",260],["miaminewtimes.com",260],["phoenixnewtimes.com",260],["westword.com",260],["nowtv.com.tr",261],["caminspector.net",262],["camwhoreshd.com",262],["camgoddess.tv",262],["gay4porn.com",264],["mypornhere.com",264],["mangovideo.*",265],["love4porn.com",265],["thotvids.com",265],["watchmdh.to",265],["celebwhore.com",265],["cluset.com",265],["sexlist.tv",265],["4kporn.xxx",265],["xhomealone.com",265],["lusttaboo.com",[265,532]],["hentai-moon.com",265],["camhub.cc",[265,691]],["mediapason.it",268],["linkspaid.com",268],["tuotromedico.com",268],["neoteo.com",268],["phoneswiki.com",268],["celebmix.com",268],["myneobuxportal.com",268],["oyungibi.com",268],["25yearslatersite.com",268],["jeshoots.com",269],["techhx.com",269],["karanapk.com",269],["flashplayer.fullstacks.net",271],["cloudapps.herokuapp.com",271],["youfiles.herokuapp.com",271],["texteditor.nsspot.net",271],["temp-mail.org",272],["asianclub.*",273],["javhdporn.net",273],["vidmoly.*",274],["comnuan.com",275],["veedi.com",276],["battleboats.io",276],["anitube.*",277],["fruitlab.com",277],["haddoz.net",277],["streamingcommunity.*",277],["garoetpos.com",277],["stiletv.it",278],["hqtv.biz",279],["liveuamap.com",280],["audycje.tokfm.pl",281],["shush.se",282],["allkpop.com",283],["empire-anime.*",[284,581,582,583,584,585]],["empire-streaming.*",[284,581,582,583]],["empire-anime.com",[284,581,582,583]],["empire-streamz.fr",[284,581,582,583]],["empire-stream.*",[284,581,582,583]],["pickcrackpasswords.blogspot.com",285],["kfrfansub.com",286],["thuglink.com",286],["voipreview.org",286],["illicoporno.com",287],["lavoixdux.com",287],["tonpornodujour.com",287],["jacquieetmichel.net",287],["swame.com",287],["vosfemmes.com",287],["voyeurfrance.net",287],["jacquieetmicheltv.net",[287,640,641]],["pogo.com",288],["cloudvideo.tv",289],["legionjuegos.org",290],["legionpeliculas.org",290],["legionprogramas.org",290],["16honeys.com",291],["elespanol.com",292],["remodelista.com",293],["audiofanzine.com",297],["uploadev.*",298],["developerinsider.co",299],["thehindu.com",300],["cambro.tv",[301,302]],["boobsradar.com",[302,399,710]],["nibelungen-kurier.de",303],["adfoc.us",304],["tackledsoul.com",304],["adrino1.bonloan.xyz",304],["vi-music.app",304],["instanders.app",304],["rokni.xyz",304],["keedabankingnews.com",304],["tea-coffee.net",304],["spatsify.com",304],["newedutopics.com",304],["getviralreach.in",304],["edukaroo.com",304],["funkeypagali.com",304],["careersides.com",304],["nayisahara.com",304],["wikifilmia.com",304],["infinityskull.com",304],["viewmyknowledge.com",304],["iisfvirtual.in",304],["starxinvestor.com",304],["jkssbalerts.com",304],["sahlmarketing.net",304],["filmypoints.in",304],["fitnessholic.net",304],["moderngyan.com",304],["sattakingcharts.in",304],["bankshiksha.in",304],["earn.mpscstudyhub.com",304],["earn.quotesopia.com",304],["money.quotesopia.com",304],["best-mobilegames.com",304],["learn.moderngyan.com",304],["bharatsarkarijobalert.com",304],["quotesopia.com",304],["creditsgoal.com",304],["bgmi32bitapk.in",304],["techacode.com",304],["trickms.com",304],["ielts-isa.edu.vn",304],["loan.punjabworks.com",304],["sptfy.be",304],["mcafee-com.com",[304,380]],["pianetamountainbike.it",305],["barchart.com",306],["modelisme.com",307],["parasportontario.ca",307],["prescottenews.com",307],["nrj-play.fr",308],["hackingwithreact.com",309],["gutekueche.at",310],["peekvids.com",311],["playvids.com",311],["pornflip.com",311],["redensarten-index.de",312],["vw-page.com",313],["viz.com",[314,315]],["0rechner.de",316],["configspc.com",317],["xopenload.me",317],["uptobox.com",317],["uptostream.com",317],["japgay.com",318],["mega-debrid.eu",319],["dreamdth.com",320],["diaridegirona.cat",322],["diariodeibiza.es",322],["diariodemallorca.es",322],["diarioinformacion.com",322],["eldia.es",322],["emporda.info",322],["farodevigo.es",322],["laopinioncoruna.es",322],["laopiniondemalaga.es",322],["laopiniondemurcia.es",322],["laopiniondezamora.es",322],["laprovincia.es",322],["levante-emv.com",322],["mallorcazeitung.es",322],["regio7.cat",322],["superdeporte.es",322],["playpaste.com",323],["cnbc.com",324],["firefaucet.win",325],["74k.io",[326,327]],["cloudwish.xyz",327],["gradehgplus.com",327],["javindo.site",327],["javindosub.site",327],["kamehaus.net",327],["movearnpre.com",327],["arabshentai.com>>",327],["javdo.cc>>",327],["javenglish.cc>>",327],["javhd.*>>",327],["javhdz.*>>",327],["roshy.tv>>",327],["sextb.*>>",327],["fullhdxxx.com",329],["pornclassic.tube",330],["tubepornclassic.com",330],["etonline.com",331],["creatur.io",331],["lookcam.*",331],["drphil.com",331],["urbanmilwaukee.com",331],["hideandseek.world",331],["myabandonware.com",331],["kendam.com",331],["wttw.com",331],["synonyms.com",331],["definitions.net",331],["hostmath.com",331],["camvideoshub.com",331],["minhaconexao.com.br",331],["home-made-videos.com",333],["amateur-couples.com",333],["slutdump.com",333],["artificialnudes.com",333],["asianal.xyz",333],["asianmassage.xyz",333],["bdsmkingdom.xyz",333],["brunettedeepthroat.com",333],["compilationtube.xyz",333],["cosplaynsfw.xyz",333],["crazytoys.xyz",333],["fikfak.net",333],["flexxporn.com",333],["handypornos.net",333],["hardcorelesbian.xyz",333],["heimporno.com",333],["instaporno.net",333],["latinabbw.xyz",333],["platinporno.com",333],["pornahegao.xyz",333],["pornobait.com",333],["pornfeet.xyz",333],["redheaddeepthroat.com",333],["romanticlesbian.com",333],["sexfilmkiste.com",333],["sexontheboat.xyz",333],["sexroute.net",333],["towheaddeepthroat.com",333],["traumporno.com",333],["dpstream.*",334],["produsat.com",335],["bluemediafiles.*",336],["12thman.com",337],["acusports.com",337],["atlantic10.com",337],["auburntigers.com",337],["baylorbears.com",337],["bceagles.com",337],["bgsufalcons.com",337],["big12sports.com",337],["bigten.org",337],["bradleybraves.com",337],["butlersports.com",337],["cmumavericks.com",337],["conferenceusa.com",337],["cyclones.com",337],["dartmouthsports.com",337],["daytonflyers.com",337],["dbupatriots.com",337],["dbusports.com",337],["denverpioneers.com",337],["fduknights.com",337],["fgcuathletics.com",337],["fightinghawks.com",337],["fightingillini.com",337],["floridagators.com",337],["friars.com",337],["friscofighters.com",337],["gamecocksonline.com",337],["goarmywestpoint.com",337],["gobison.com",337],["goblueraiders.com",337],["gobobcats.com",337],["gocards.com",337],["gocreighton.com",337],["godeacs.com",337],["goexplorers.com",337],["goetbutigers.com",337],["gofrogs.com",337],["gogriffs.com",337],["gogriz.com",337],["golobos.com",337],["gomarquette.com",337],["gopack.com",337],["gophersports.com",337],["goprincetontigers.com",337],["gopsusports.com",337],["goracers.com",337],["goshockers.com",337],["goterriers.com",337],["gotigersgo.com",337],["gousfbulls.com",337],["govandals.com",337],["gowyo.com",337],["goxavier.com",337],["gozags.com",337],["gozips.com",337],["griffinathletics.com",337],["guhoyas.com",337],["gwusports.com",337],["hailstate.com",337],["hamptonpirates.com",337],["hawaiiathletics.com",337],["hokiesports.com",337],["huskers.com",337],["icgaels.com",337],["iuhoosiers.com",337],["jsugamecocksports.com",337],["longbeachstate.com",337],["loyolaramblers.com",337],["lrtrojans.com",337],["lsusports.net",337],["morrisvillemustangs.com",337],["msuspartans.com",337],["muleriderathletics.com",337],["mutigers.com",337],["navysports.com",337],["nevadawolfpack.com",337],["niuhuskies.com",337],["nkunorse.com",337],["nuhuskies.com",337],["nusports.com",337],["okstate.com",337],["olemisssports.com",337],["omavs.com",337],["ovcsports.com",337],["owlsports.com",337],["purduesports.com",337],["redstormsports.com",337],["richmondspiders.com",337],["sfajacks.com",337],["shupirates.com",337],["siusalukis.com",337],["smcgaels.com",337],["smumustangs.com",337],["soconsports.com",337],["soonersports.com",337],["themw.com",337],["tulsahurricane.com",337],["txst.com",337],["txstatebobcats.com",337],["ubbulls.com",337],["ucfknights.com",337],["ucirvinesports.com",337],["uconnhuskies.com",337],["uhcougars.com",337],["uicflames.com",337],["umterps.com",337],["uncwsports.com",337],["unipanthers.com",337],["unlvrebels.com",337],["uoflsports.com",337],["usdtoreros.com",337],["utahstateaggies.com",337],["utepathletics.com",337],["utrockets.com",337],["uvmathletics.com",337],["uwbadgers.com",337],["villanova.com",337],["wkusports.com",337],["wmubroncos.com",337],["woffordterriers.com",337],["1pack1goal.com",337],["bcuathletics.com",337],["bubraves.com",337],["goblackbears.com",337],["golightsgo.com",337],["gomcpanthers.com",337],["goutsa.com",337],["mercerbears.com",337],["pirateblue.com",337],["pirateblue.net",337],["pirateblue.org",337],["quinnipiacbobcats.com",337],["towsontigers.com",337],["tribeathletics.com",337],["tribeclub.com",337],["utepminermaniacs.com",337],["utepminers.com",337],["wkutickets.com",337],["aopathletics.org",337],["atlantichockeyonline.com",337],["bigsouthnetwork.com",337],["bigsouthsports.com",337],["chawomenshockey.com",337],["dbupatriots.org",337],["drakerelays.org",337],["ecac.org",337],["ecacsports.com",337],["emueagles.com",337],["emugameday.com",337],["gculopes.com",337],["godrakebulldog.com",337],["godrakebulldogs.com",337],["godrakebulldogs.net",337],["goeags.com",337],["goislander.com",337],["goislanders.com",337],["gojacks.com",337],["gomacsports.com",337],["gseagles.com",337],["hubison.com",337],["iowaconference.com",337],["ksuowls.com",337],["lonestarconference.org",337],["mascac.org",337],["midwestconference.org",337],["mountaineast.org",337],["niu-pack.com",337],["nulakers.ca",337],["oswegolakers.com",337],["ovcdigitalnetwork.com",337],["pacersports.com",337],["rmacsports.org",337],["rollrivers.com",337],["samfordsports.com",337],["uncpbraves.com",337],["usfdons.com",337],["wiacsports.com",337],["alaskananooks.com",337],["broncathleticfund.com",337],["cameronaggies.com",337],["columbiacougars.com",337],["etownbluejays.com",337],["gobadgers.ca",337],["golancers.ca",337],["gometrostate.com",337],["gothunderbirds.ca",337],["kentstatesports.com",337],["lehighsports.com",337],["lopers.com",337],["lycoathletics.com",337],["lycomingathletics.com",337],["maraudersports.com",337],["mauiinvitational.com",337],["msumavericks.com",337],["nauathletics.com",337],["nueagles.com",337],["nwusports.com",337],["oceanbreezenyc.org",337],["patriotathleticfund.com",337],["pittband.com",337],["principiaathletics.com",337],["roadrunnersathletics.com",337],["sidearmsocial.com",337],["snhupenmen.com",337],["stablerarena.com",337],["stoutbluedevils.com",337],["uwlathletics.com",337],["yumacs.com",337],["collegefootballplayoff.com",337],["csurams.com",337],["cubuffs.com",337],["gobearcats.com",337],["gohuskies.com",337],["mgoblue.com",337],["osubeavers.com",337],["pittsburghpanthers.com",337],["rolltide.com",337],["texassports.com",337],["thesundevils.com",337],["uclabruins.com",337],["wvuathletics.com",337],["wvusports.com",337],["arizonawildcats.com",337],["calbears.com",337],["cuse.com",337],["georgiadogs.com",337],["goducks.com",337],["goheels.com",337],["gostanford.com",337],["insidekstatesports.com",337],["insidekstatesports.info",337],["insidekstatesports.net",337],["insidekstatesports.org",337],["k-stateathletics.com",337],["k-statefootball.net",337],["k-statefootball.org",337],["k-statesports.com",337],["k-statesports.net",337],["k-statesports.org",337],["k-statewomenshoops.com",337],["k-statewomenshoops.net",337],["k-statewomenshoops.org",337],["kstateathletics.com",337],["kstatefootball.net",337],["kstatefootball.org",337],["kstatesports.com",337],["kstatewomenshoops.com",337],["kstatewomenshoops.net",337],["kstatewomenshoops.org",337],["ksuathletics.com",337],["ksusports.com",337],["scarletknights.com",337],["showdownforrelief.com",337],["syracusecrunch.com",337],["texastech.com",337],["theacc.com",337],["ukathletics.com",337],["usctrojans.com",337],["utahutes.com",337],["utsports.com",337],["wsucougars.com",337],["vidlii.com",[337,363]],["tricksplit.io",337],["fangraphs.com",338],["stern.de",339],["geo.de",339],["brigitte.de",339],["schoener-wohnen.de",339],["welt.de",340],["tvspielfilm.de",[341,342,343,344]],["tvtoday.de",[341,342,343,344]],["chip.de",[341,342,343,344]],["focus.de",[341,342,343,344]],["fitforfun.de",[341,342,343,344]],["n-tv.de",345],["player.rtl2.de",346],["planetaminecraft.com",347],["cravesandflames.com",348],["codesnse.com",348],["flyad.vip",348],["lapresse.ca",349],["kolyoom.com",350],["ilovephd.com",350],["negumo.com",351],["games.wkb.jp",[352,353]],["kenshi.fandom.com",355],["hausbau-forum.de",356],["homeairquality.org",356],["call4cloud.nl",356],["fake-it.ws",357],["laksa19.github.io",358],["1shortlink.com",359],["u-s-news.com",360],["luscious.net",361],["makemoneywithurl.com",362],["junkyponk.com",362],["healthfirstweb.com",362],["vocalley.com",362],["yogablogfit.com",362],["howifx.com",362],["en.financerites.com",362],["mythvista.com",362],["livenewsflix.com",362],["cureclues.com",362],["apekite.com",362],["enit.in",362],["iammagnus.com",363],["dailyvideoreports.net",363],["unityassets4free.com",363],["docer.*",364],["resetoff.pl",364],["sexodi.com",364],["cdn77.org",365],["momxxxsex.com",366],["penisbuyutucum.net",366],["ujszo.com",367],["newsmax.com",368],["nadidetarifler.com",369],["siz.tv",369],["suzylu.co.uk",[370,371]],["onworks.net",372],["yabiladi.com",372],["downloadsoft.net",373],["newsobserver.com",374],["arkadiumhosted.com",374],["testlanguages.com",375],["newsinlevels.com",375],["videosinlevels.com",375],["procinehub.com",376],["bookmystrip.com",376],["imagereviser.com",377],["pubgaimassist.com",378],["gyanitheme.com",378],["tech.trendingword.com",378],["blog.potterworld.co",378],["hipsonyc.com",378],["tech.pubghighdamage.com",378],["blog.itijobalert.in",378],["techkhulasha.com",378],["jiocinema.com",378],["rapid-cloud.co",378],["uploadmall.com",378],["4funbox.com",379],["nephobox.com",379],["1024tera.com",379],["terabox.*",379],["starkroboticsfrc.com",380],["sinonimos.de",380],["antonimos.de",380],["quesignifi.ca",380],["tiktokrealtime.com",380],["tiktokcounter.net",380],["tpayr.xyz",380],["poqzn.xyz",380],["ashrfd.xyz",380],["rezsx.xyz",380],["tryzt.xyz",380],["ashrff.xyz",380],["rezst.xyz",380],["dawenet.com",380],["erzar.xyz",380],["waezm.xyz",380],["waezg.xyz",380],["blackwoodacademy.org",380],["cryptednews.space",380],["vivuq.com",380],["swgop.com",380],["vbnmll.com",380],["telcoinfo.online",380],["dshytb.com",380],["btcbitco.in",[380,381]],["btcsatoshi.net",380],["cempakajaya.com",380],["crypto4yu.com",380],["readbitcoin.org",380],["wiour.com",380],["finish.addurl.biz",380],["aiimgvlog.fun",[380,384]],["laweducationinfo.com",380],["savemoneyinfo.com",380],["worldaffairinfo.com",380],["godstoryinfo.com",380],["successstoryinfo.com",380],["cxissuegk.com",380],["learnmarketinfo.com",380],["bhugolinfo.com",380],["armypowerinfo.com",380],["rsgamer.app",380],["phonereviewinfo.com",380],["makeincomeinfo.com",380],["gknutshell.com",380],["vichitrainfo.com",380],["workproductivityinfo.com",380],["dopomininfo.com",380],["hostingdetailer.com",380],["fitnesssguide.com",380],["tradingfact4u.com",380],["cryptofactss.com",380],["softwaredetail.com",380],["artoffocas.com",380],["insurancesfact.com",380],["travellingdetail.com",380],["advertisingexcel.com",380],["allcryptoz.net",380],["batmanfactor.com",380],["beautifulfashionnailart.com",380],["crewbase.net",380],["documentaryplanet.xyz",380],["crewus.net",380],["gametechreviewer.com",380],["midebalonu.net",380],["misterio.ro",380],["phineypet.com",380],["seory.xyz",380],["shinbhu.net",380],["shinchu.net",380],["substitutefor.com",380],["talkforfitness.com",380],["thefitbrit.co.uk",380],["thumb8.net",380],["thumb9.net",380],["topcryptoz.net",380],["uniqueten.net",380],["ultraten.net",380],["exactpay.online",380],["quins.us",380],["kiddyearner.com",380],["bildirim.*",383],["arahdrive.com",384],["appsbull.com",385],["diudemy.com",385],["maqal360.com",[385,386,387]],["lifesurance.info",388],["akcartoons.in",389],["cybercityhelp.in",389],["dl.apkmoddone.com",390],["phongroblox.com",390],["fuckingfast.net",391],["buzzheavier.com",391],["tickhosting.com",392],["in91vip.win",393],["datavaults.co",394],["t-online.de",396],["upornia.*",[397,398]],["bobs-tube.com",399],["pornohirsch.net",400],["bembed.net",401],["embedv.net",401],["javguard.club",401],["listeamed.net",401],["v6embed.xyz",401],["vembed.*",401],["vid-guard.com",401],["vinomo.xyz",401],["nekolink.site",[402,403]],["141jav.com",404],["141tube.com",404],["aagmaal.com",404],["camcam.cc",404],["javneon.tv",404],["javsaga.ninja",404],["torrentkitty.one",404],["pixsera.net",405],["jnews5.com",406],["pc-builds.com",407],["reuters.com",407],["today.com",407],["videogamer.com",407],["wrestlinginc.com",407],["azcentral.com",408],["greenbaypressgazette.com",408],["palmbeachpost.com",408],["usatoday.com",[408,409]],["ydr.com",408],["247sports.com",410],["indiatimes.com",411],["netzwelt.de",412],["filmibeat.com",413],["goodreturns.in",413],["mykhel.com",413],["daemonanime.net",413],["luckydice.net",413],["weatherwx.com",413],["sattaguess.com",413],["winshell.de",413],["rosasidan.ws",413],["upiapi.in",413],["networkhint.com",413],["thichcode.net",413],["texturecan.com",413],["tikmate.app",[413,622]],["arcaxbydz.id",413],["quotesshine.com",413],["worldhistory.org",414],["arcade.buzzrtv.com",415],["arcade.dailygazette.com",415],["arcade.lemonde.fr",415],["arena.gamesforthebrain.com",415],["bestpuzzlesandgames.com",415],["cointiply.arkadiumarena.com",415],["gamelab.com",415],["gameplayneo.com",415],["games.abqjournal.com",415],["games.arkadium.com",415],["games.amny.com",415],["games.bellinghamherald.com",415],["games.besthealthmag.ca",415],["games.bnd.com",415],["games.boston.com",415],["games.bostonglobe.com",415],["games.bradenton.com",415],["games.centredaily.com",415],["games.charlottegames.cnhinews.com",415],["games.crosswordgiant.com",415],["games.dailymail.co.uk",415],["games.dallasnews.com",415],["games.daytondailynews.com",415],["games.denverpost.com",415],["games.everythingzoomer.com",415],["games.fresnobee.com",415],["games.gameshownetwork.com",415],["games.get.tv",415],["games.greatergood.com",415],["games.heraldonline.com",415],["games.heraldsun.com",415],["games.idahostatesman.com",415],["games.insp.com",415],["games.islandpacket.com",415],["games.journal-news.com",415],["games.kansas.com",415],["games.kansascity.com",415],["games.kentucky.com",415],["games.lancasteronline.com",415],["games.ledger-enquirer.com",415],["games.macon.com",415],["games.mashable.com",415],["games.mercedsunstar.com",415],["games.metro.us",415],["games.metv.com",415],["games.miamiherald.com",415],["games.modbee.com",415],["games.moviestvnetwork.com",415],["games.myrtlebeachonline.com",415],["games.games.newsgames.parade.com",415],["games.pressdemocrat.com",415],["games.puzzlebaron.com",415],["games.puzzler.com",415],["games.puzzles.ca",415],["games.qns.com",415],["games.readersdigest.ca",415],["games.sacbee.com",415],["games.sanluisobispo.com",415],["games.sixtyandme.com",415],["games.sltrib.com",415],["games.springfieldnewssun.com",415],["games.star-telegram.com",415],["games.startribune.com",415],["games.sunherald.com",415],["games.theadvocate.com",415],["games.thenewstribune.com",415],["games.theolympian.com",415],["games.theportugalnews.com",415],["games.thestar.com",415],["games.thestate.com",415],["games.tri-cityherald.com",415],["games.triviatoday.com",415],["games.usnews.com",415],["games.word.tips",415],["games.wordgenius.com",415],["games.wtop.com",415],["jeux.meteocity.com",415],["juegos.as.com",415],["juegos.elnuevoherald.com",415],["juegos.elpais.com",415],["philly.arkadiumarena.com",415],["play.dictionary.com",415],["puzzles.bestforpuzzles.com",415],["puzzles.centralmaine.com",415],["puzzles.crosswordsolver.org",415],["puzzles.independent.co.uk",415],["puzzles.nola.com",415],["puzzles.pressherald.com",415],["puzzles.standard.co.uk",415],["puzzles.sunjournal.com",415],["arkadium.com",416],["abysscdn.com",[417,418]],["turtleviplay.xyz",419],["mixdrop.*",420],["ai.hubtoday.app",421],["news.now.com",422],["qub.ca",423],["gostyn24.pl",424],["lared.cl",425],["atozmath.com",[425,449,450,451,452,453,454]],["pcbolsa.com",426],["hdfilmizlesen.com",427],["watch.rkplayer.xyz",428],["arcai.com",429],["my-code4you.blogspot.com",430],["flickr.com",431],["firefile.cc",432],["pestleanalysis.com",432],["kochamjp.pl",432],["tutorialforlinux.com",432],["whatsaero.com",432],["animeblkom.net",[432,446]],["blkom.com",432],["globes.co.il",[433,434]],["jardiner-malin.fr",435],["tw-calc.net",436],["ohmybrush.com",437],["talkceltic.net",438],["mentalfloss.com",439],["uprafa.com",440],["cube365.net",441],["wwwfotografgotlin.blogspot.com",442],["freelistenonline.com",442],["badassdownloader.com",443],["quickporn.net",444],["yellowbridge.com",445],["aosmark.com",447],["ctrlv.*",448],["newyorker.com",455],["brighteon.com",[456,457]],["more.tv",458],["video1tube.com",459],["alohatube.xyz",459],["4players.de",460],["onlinesoccermanager.com",460],["fshost.me",461],["link.cgtips.org",462],["hentaicloud.com",463],["paperzonevn.com",465],["9jarock.org",466],["fzmovies.info",466],["fztvseries.ng",466],["netnaijas.com",466],["hentaienglish.com",467],["hentaiporno.xxx",467],["venge.io",[468,469]],["its.porn",[470,471]],["atv.at",472],["2ndrun.tv",473],["rackusreads.com",473],["teachmemicro.com",473],["willcycle.com",473],["kusonime.com",[474,475]],["123movieshd.*",476],["imgur.com",[477,478,750]],["hentai-party.com",479],["hentaicomics.pro",479],["uproxy.*",480],["animesa.*",481],["subtitleone.cc",482],["mysexgames.com",483],["ancient-origins.*",484],["cinecalidad.*",[485,486]],["xnxx.*",487],["xvideos.*",487],["gdr-online.com",488],["mmm.dk",489],["iqiyi.com",[490,491,612]],["m.iqiyi.com",492],["nbcolympics.com",493],["apkhex.com",494],["indiansexstories2.net",495],["issstories.xyz",495],["1340kbbr.com",496],["gorgeradio.com",496],["kduk.com",496],["kedoam.com",496],["kejoam.com",496],["kelaam.com",496],["khsn1230.com",496],["kjmx.rocks",496],["kloo.com",496],["klooam.com",496],["klykradio.com",496],["kmed.com",496],["kmnt.com",496],["kpnw.com",496],["kppk983.com",496],["krktcountry.com",496],["ktee.com",496],["kwro.com",496],["kxbxfm.com",496],["thevalley.fm",496],["quizlet.com",497],["dsocker1234.blogspot.com",498],["schoolcheats.net",[499,500]],["mgnet.xyz",501],["designtagebuch.de",502],["pixroute.com",503],["uploady.io",504],["calculator-online.net",505],["porngames.club",506],["sexgames.xxx",506],["111.90.159.132",507],["mobile-tracker-free.com",508],["social-unlock.com",509],["superpsx.com",510],["ninja.io",511],["sourceforge.net",512],["samfirms.com",513],["rapelust.com",514],["vtube.to",514],["desitelugusex.com",514],["dvdplay.*",514],["xvideos-downloader.net",514],["xxxvideotube.net",514],["sdefx.cloud",514],["nozomi.la",514],["banned.video",515],["madmaxworld.tv",515],["androidpolice.com",515],["babygaga.com",515],["backyardboss.net",515],["carbuzz.com",515],["cbr.com",515],["collider.com",515],["dualshockers.com",515],["footballfancast.com",515],["footballleagueworld.co.uk",515],["gamerant.com",515],["givemesport.com",515],["hardcoregamer.com",515],["hotcars.com",515],["howtogeek.com",515],["makeuseof.com",515],["moms.com",515],["movieweb.com",515],["pocket-lint.com",515],["pocketnow.com",515],["screenrant.com",515],["simpleflying.com",515],["thegamer.com",515],["therichest.com",515],["thesportster.com",515],["thethings.com",515],["thetravel.com",515],["topspeed.com",515],["xda-developers.com",515],["huffpost.com",516],["ingles.com",517],["spanishdict.com",517],["surfline.com",[518,519]],["play.tv3.ee",520],["play.tv3.lt",520],["play.tv3.lv",[520,521]],["tv3play.skaties.lv",520],["bulbagarden.net",522],["hollywoodlife.com",523],["mat6tube.com",524],["hotabis.com",525],["root-nation.com",525],["italpress.com",525],["airsoftmilsimnews.com",525],["artribune.com",525],["newtumbl.com",526],["apkmaven.*",527],["aruble.net",528],["nevcoins.club",529],["mail.com",530],["gmx.*",531],["mangakita.id",533],["avpgalaxy.net",534],["panda-novel.com",535],["lightsnovel.com",535],["eaglesnovel.com",535],["pandasnovel.com",535],["ewrc-results.com",536],["kizi.com",537],["cyberscoop.com",538],["fedscoop.com",538],["jeep-cj.com",539],["sponsorhunter.com",540],["cloudcomputingtopics.net",541],["likecs.com",542],["tiscali.it",543],["linkspy.cc",544],["adshnk.com",545],["chattanoogan.com",546],["adsy.pw",547],["playstore.pw",547],["windowspro.de",548],["tvtv.ca",549],["tvtv.us",549],["mydaddy.cc",550],["roadtrippin.fr",551],["vavada5com.com",552],["anyporn.com",[553,570]],["bravoporn.com",553],["bravoteens.com",553],["crocotube.com",553],["hellmoms.com",553],["hellporno.com",553],["sex3.com",553],["tubewolf.com",553],["xbabe.com",553],["xcum.com",553],["zedporn.com",553],["imagetotext.info",554],["infokik.com",555],["freepik.com",556],["ddwloclawek.pl",[557,558]],["www.seznam.cz",559],["deezer.com",560],["my-subs.co",561],["plaion.com",562],["slideshare.net",[563,564]],["ustreasuryyieldcurve.com",565],["businesssoftwarehere.com",566],["goo.st",566],["freevpshere.com",566],["softwaresolutionshere.com",566],["gamereactor.*",568],["madoohd.com",569],["doomovie-hd.*",569],["staige.tv",571],["androidadult.com",572],["streamvid.net",573],["watchtv24.com",574],["cellmapper.net",575],["medscape.com",576],["newscon.org",[577,578]],["wheelofgold.com",579],["drakecomic.*",579],["app.blubank.com",580],["mobileweb.bankmellat.ir",580],["ccthesims.com",587],["chromeready.com",587],["dtbps3games.com",587],["illustratemagazine.com",587],["uknip.co.uk",587],["vod.pl",588],["megadrive-emulator.com",589],["tvhay.*",[590,591]],["moviesapi.club",592],["watchx.top",592],["digimanie.cz",593],["svethardware.cz",593],["srvy.ninja",594],["chat.tchatche.com",[595,596]],["cnn.com",[597,598,599]],["news.bg",600],["edmdls.com",601],["freshremix.net",601],["scenedl.org",601],["trakt.tv",602],["shroomers.app",603],["classicalradio.com",604],["di.fm",604],["jazzradio.com",604],["radiotunes.com",604],["rockradio.com",604],["zenradio.com",604],["getthit.com",605],["techedubyte.com",606],["iwanttfc.com",607],["nutraingredients-asia.com",608],["nutraingredients-latam.com",608],["nutraingredients-usa.com",608],["nutraingredients.com",608],["ozulscansen.com",609],["nexusmods.com",610],["lookmovie.*",611],["lookmovie2.to",611],["biletomat.pl",613],["hextank.io",[614,615]],["filmizlehdfilm.com",[616,617,618,619]],["filmizletv.*",[616,617,618,619]],["fullfilmizle.cc",[616,617,618,619]],["gofilmizle.net",[616,617,618,619]],["cimanow.cc",620],["bgmiupdate.com.in",620],["freex2line.online",621],["btvplus.bg",623],["sagewater.com",624],["redlion.net",624],["filmweb.pl",625],["satdl.com",626],["vidstreaming.xyz",627],["everand.com",628],["myradioonline.pl",629],["cbs.com",630],["paramountplus.com",630],["colourxh.site",631],["fullxh.com",631],["galleryxh.site",631],["megaxh.com",631],["movingxh.world",631],["seexh.com",631],["unlockxh4.com",631],["valuexh.life",631],["xhaccess.com",631],["xhadult2.com",631],["xhadult3.com",631],["xhadult4.com",631],["xhadult5.com",631],["xhamster.*",631],["xhamster1.*",631],["xhamster10.*",631],["xhamster11.*",631],["xhamster12.*",631],["xhamster13.*",631],["xhamster14.*",631],["xhamster15.*",631],["xhamster16.*",631],["xhamster17.*",631],["xhamster18.*",631],["xhamster19.*",631],["xhamster20.*",631],["xhamster2.*",631],["xhamster3.*",631],["xhamster4.*",631],["xhamster42.*",631],["xhamster46.com",631],["xhamster5.*",631],["xhamster7.*",631],["xhamster8.*",631],["xhamsterporno.mx",631],["xhbig.com",631],["xhbranch5.com",631],["xhchannel.com",631],["xhdate.world",631],["xhlease.world",631],["xhmoon5.com",631],["xhofficial.com",631],["xhopen.com",631],["xhplanet1.com",631],["xhplanet2.com",631],["xhreal2.com",631],["xhreal3.com",631],["xhspot.com",631],["xhtotal.com",631],["xhtree.com",631],["xhvictory.com",631],["xhwebsite.com",631],["xhwebsite2.com",631],["xhwebsite5.com",631],["xhwide1.com",631],["xhwide2.com",631],["xhwide5.com",631],["file-upload.net",632],["tunein.com",633],["acortalo.*",[635,636,637,638]],["acortar.*",[635,636,637,638]],["hentaihaven.xxx",639],["jacquieetmicheltv2.net",641],["a2zapk.*",642],["fcportables.com",[643,644]],["emurom.net",645],["freethesaurus.com",[646,647]],["thefreedictionary.com",[646,647]],["oeffentlicher-dienst.info",648],["im9.eu",[649,650]],["dcdlplayer8a06f4.xyz",651],["ultimate-guitar.com",652],["claimbits.net",653],["sexyscope.net",654],["kickassanime.*",655],["recherche-ebook.fr",656],["virtualdinerbot.com",656],["zonebourse.com",657],["pink-sluts.net",658],["andhrafriends.com",659],["benzinpreis.de",660],["defenseone.com",661],["govexec.com",661],["nextgov.com",661],["route-fifty.com",661],["sharing.wtf",662],["wetter3.de",663],["esportivos.fun",664],["cosmonova-broadcast.tv",665],["538.nl",666],["hartvannederland.nl",666],["kijk.nl",666],["shownieuws.nl",666],["vandaaginside.nl",666],["rock.porn",[667,668]],["videzz.net",[669,670]],["ezaudiobookforsoul.com",671],["club386.com",672],["decompiler.com",[673,674]],["littlebigsnake.com",675],["easyfun.gg",676],["smailpro.com",677],["ilgazzettino.it",678],["ilmessaggero.it",678],["3bmeteo.com",[679,680]],["mconverter.eu",681],["lover937.net",682],["10gb.vn",683],["pes6.es",684],["tactics.tools",[685,686]],["boundhub.com",687],["reliabletv.me",688],["jakondo.ru",689],["trueachievements.com",689],["truesteamachievements.com",689],["truetrophies.com",689],["av1encodes.com",689],["filecrypt.*",690],["wired.com",692],["spankbang.*",[693,694,695,754,755]],["hulu.com",[696,697,698]],["hanime.tv",699],["nhentai.net",[700,701,702]],["pouvideo.*",703],["povvideo.*",703],["povw1deo.*",703],["povwideo.*",703],["powv1deo.*",703],["powvibeo.*",703],["powvideo.*",703],["powvldeo.*",703],["powcloud.org",704],["primevideo.com",705],["read.amazon.*",[705,721]],["anonymfile.com",706],["gofile.to",706],["dotycat.com",707],["rateyourmusic.com",708],["reporterpb.com.br",709],["blog-dnz.com",711],["18adultgames.com",712],["colnect.com",[713,714]],["adultgamesworld.com",715],["servustv.com",[716,717]],["reviewdiv.com",718],["parametric-architecture.com",719],["voiceofdenton.com",720],["concealednation.org",720],["askattest.com",722],["opensubtitles.com",723],["savefiles.com",724],["streamup.ws",725],["pfps.gg",726],["goodstream.one",727],["lecrabeinfo.net",728],["cerberusapp.com",729],["smashkarts.io",730],["beamng.wesupply.cx",731],["wowtv.de",[732,733]],["jsfiddle.net",[734,735]],["musicbusinessworldwide.com",736],["mahfda.com",737],["agar.live",738],["dailymotion.com",739],["scribd.com",740],["live.arynews.tv",741],["pornlore.com",[742,743]],["91porn.com",744],["www.google.*",745],["tacobell.com",746],["zefoy.com",747],["cnet.com",748],["trendyol.com",[751,752]],["trendyol-milla.com",[751,752]],["natgeotv.com",753],["globo.com",756],["linklog.tiagorangel.com",758],["wayfair.com",759]]);
const exceptionsMap = new Map([["cloudflare.com",[0]],["pingit.com",[183]],["loan.bgmi32bitapk.in",[304]],["lookmovie.studio",[611]]]);
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
    try { setConstant(...argsList[i]); }
    catch { }
}

/******************************************************************************/

// End of local scope
})();

void 0;
