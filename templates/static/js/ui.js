// =========================================================================
// Theme
// =========================================================================
var TK = 'sb-theme-v2';

function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    $('theme-btn').textContent = t === 'dark' ? 'L' : 'D';
    localStorage.setItem(TK, t);
}

function toggleTheme() {
    applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
}

applyTheme(localStorage.getItem(TK) || 'dark');

// =========================================================================
// Mobile Navigation
// =========================================================================
function toggleMenu() {
    var tabs = $('nav-tabs');
    tabs.classList.toggle('open');
    $('menu-btn').textContent = tabs.classList.contains('open') ? '\u00d7' : '\u2630';
}

document.addEventListener('click', function(e) {
    var tabs = $('nav-tabs');
    if (tabs && tabs.classList.contains('open') && !tabs.contains(e.target) && e.target !== $('menu-btn')) {
        tabs.classList.remove('open');
        $('menu-btn').textContent = '\u2630';
    }
});

// =========================================================================
// Tab Switching
// =========================================================================
var _embedUrls = {wetty:'', fb:'', jf:''};

function sw(id, btn) {
    qsa('.panel').forEach(function(p) { p.classList.remove('active'); });
    qsa('.ntab').forEach(function(t) { t.classList.remove('active'); });
    $('panel-'+id).classList.add('active');
    if (btn) btn.classList.add('active');
    $('nav-tabs').classList.remove('open');
    $('menu-btn').textContent = '\u2630';
    
    // Load embeds on first visit
    var pm = {terminal:'wetty', files:'fb', jellyfin:'jf'};
    var prefix = pm[id];
    if (prefix && _embedUrls[prefix]) {
        var frame = $(prefix+'-frame');
        if (frame && frame.src === 'about:blank') {
            frame.src = _embedUrls[prefix];
            $(prefix+'-offline').style.display = 'none';
        }
    }
    if (id === 'browser' && _nekoRunning && _nekoUrl) {
        var nf = $('neko-frame');
        if (nf && nf.src === 'about:blank') {
            nf.src = _nekoUrl; 
            nf.style.display = 'block';
            $('neko-offline').style.display = 'none';
        }
    }
}

// =========================================================================
// Embed Helpers
// =========================================================================
function loadEmbed(prefix) {
    var url = _embedUrls[prefix]; 
    if (!url) return;
    var frame = $(prefix+'-frame'); 
    var off = $(prefix+'-offline');
    if (frame) { 
        frame.src = url; 
        frame.style.display = 'block'; 
    }
    if (off)   off.style.display = 'none';
}

function reloadEmbed(frameId) {
    var f = $(frameId); 
    if (!f || f.src === 'about:blank') return;
    var src = f.src; 
    f.src = 'about:blank'; 
    setTimeout(function() { f.src = src; }, 100);
}

function setEmbedState(prefix, running, url) {
    _embedUrls[prefix] = url;
    var frame = $(prefix+'-frame'); 
    var off = $(prefix+'-offline');
    var badge = $(prefix+'-badge'); 
    var win = $(prefix+'-win');
    var panelId = prefix==='wetty'?'terminal':prefix==='fb'?'files':'jellyfin';
    var panel = $('panel-'+panelId);
    
    if (running && url) {
        if (frame) frame.style.display = 'block';
        if (off)   off.style.display = 'none';
        if (panel && panel.classList.contains('active') && frame && frame.src==='about:blank') frame.src = url;
        if (win)   win.href = url;
        if (badge) { badge.textContent='Running'; badge.className='sbadge on'; }
    } else {
        if (frame) { frame.style.display='none'; frame.src='about:blank'; }
        if (off)   off.style.display='flex';
        if (badge) { badge.textContent='Stopped'; badge.className='sbadge off'; }
    }
}
