//"use strict";

cs_default = function (bg2csData = '') {

if (bg2csData && bg2csData.cs_param)
  cs_param = bg2csData.cs_param;

if (!(csDone || csDoneOnce)) {

if (window.location.hostname.match(/\.(dk|fi|se)$/)) {//denmark/finland/sweden

if (matchDomain('berlingske.dk')) {
  let paywall = document.querySelector('div#paywall');
  removeDOMElement(paywall);
  let ads = 'div.advert-unit';
  hideDOMStyle(ads);
}

else if (matchDomain('dn.se')) {
  let url = window.location.href;
  getArchive(url, 'div.paywall-wrapper', '', 'article');
  let ads = 'div.bad';
  hideDOMStyle(ads);
}

else if (matchDomain('etc.se')) {
  let paywall = document.querySelector('section.prose-feature > section.teaser-section');
  if (paywall) {
    paywall.classList.remove('teaser-section');
    paywall.parentNode.querySelectorAll('.hidden').forEach(e => e.classList.remove('hidden'));
  }
  let ads = 'div[class$="-ad"], article section.font-sans';
  hideDOMStyle(ads);
  let video_iframes = document.querySelectorAll('div.embed-block > iframe[width][height]');
  for (let elem of video_iframes) {
    if (elem.width > 1000) {
      let ratio = elem.width / (mobile ? 320 : 640);
      elem.width = elem.width / ratio;
      elem.height = elem.height / ratio;
    }
  }
}

else if (matchDomain('suomensotilas.fi')) {
  let obscured = document.querySelector('div.epfl-pw-obscured');
  if (obscured)
    obscured.classList.remove('epfl-pw-obscured');
}

else
  csDone = true;
}

} // end csDone(Once)

ads_hide();
leaky_paywall_unhide();

} // end cs_default function
