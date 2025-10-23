/*******************************************************************************

    uBlock Origin Lite - a comprehensive, MV3-compliant content blocker
    Copyright (C) 2019-present Raymond Hill

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

// ruleset: shot-power-scraper-custom

// Important!
// Isolate from global scope
(function uBOL_cssSpecificImports() {

/******************************************************************************/

const argsList = ["","div[style=\"background-color: rgba(0, 0, 0, 0.4); position: fixed; min-width: 100%; min-height: 100%; inset: 0px; z-index: 999999;\"]"];
const argsSeqs = [0,1];
const hostnamesMap = new Map([["cnn.com",1]]);
const hasEntities = false;

self.specificImports = self.specificImports || [];
self.specificImports.push({ argsList, argsSeqs, hostnamesMap, hasEntities });

/******************************************************************************/

})();

/******************************************************************************/
