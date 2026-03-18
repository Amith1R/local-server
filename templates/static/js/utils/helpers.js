// =========================================================================
// DOM Helpers
// =========================================================================
function $(id) { return document.getElementById(id); }
function qs(sel) { return document.querySelector(sel); }
function qsa(sel) { return document.querySelectorAll(sel); }

// =========================================================================
// Formatting Helpers
// =========================================================================
function fmtKB(kb) { 
    return kb >= 1024 ? (kb/1024).toFixed(1)+' MB/s' : kb.toFixed(1)+' KB/s'; 
}

function fmtGB(gb) { 
    return gb >= 1 ? gb.toFixed(2)+' GB' : ((gb||0)*1024).toFixed(0)+' MB'; 
}

function cc(p) { 
    return p >= 85 ? 'r' : p >= 65 ? 'y' : 'g'; 
}

// =========================================================================
// UI State Helpers
// =========================================================================
function setDot(id, state) {
    var e = $(id); 
    if (!e) return;
    e.className = 'sdot ' + (state === 'on' ? 'on' : state === 'warn' ? 'warn' : 'off');
}

function setBdg(id, txt, cls) {
    var e = $(id); 
    if (!e) return;
    e.textContent = txt; 
    e.className = 'sbadge ' + (cls || '');
}

function setTxt(id, v) { 
    var e = $(id); 
    if (e) e.textContent = v; 
}

function setClass(id, cls) { 
    var e = $(id); 
    if (e) e.className = cls; 
}

// =========================================================================
// Clock
// =========================================================================
function updateClock() {
    var now = new Date();
    var h = String(now.getHours()).padStart(2,'0');
    var m = String(now.getMinutes()).padStart(2,'0');
    var s = String(now.getSeconds()).padStart(2,'0');
    setTxt('nav-time', h+':'+m+':'+s);
}
setInterval(updateClock, 1000);
updateClock();
