// =========================================================================
// Neko Browser Controls
// =========================================================================
var _nekoRunning = false, _nekoUrl = '', _nekoStarting = false;
var _nekoCurrentDlPath = '/mnt/exstore/Downloads';
var NEKO_PATH_PRESETS = [
    '/mnt/exstore/Downloads','/mnt/exstore/Movies','/mnt/exstore/TVShows',
    '/mnt/exstore/TVShows/Korean','/mnt/exstore/Music',
];

function setNekoState(running, url, dlPath, stats) {
    _nekoRunning = running; 
    _nekoUrl = url;
    
    if (dlPath) {
        _nekoCurrentDlPath = dlPath;
        ['neko-dl-pill','neko-offline-pill','ctl-neko-dl-path'].forEach(function(id) {
            var e = $(id); 
            if (e) e.textContent = dlPath;
        });
        var ni = $('neko-path-inp'); 
        if (ni) ni.placeholder = dlPath;
    }
    
    var nd = $('nd-neko'); 
    if (nd) nd.className = 'ntab-dot '+(running?'on':'off');
    
    var badge = $('neko-badge'); 
    var ctlBadge = $('neko-ctl-badge');
    var frame = $('neko-frame'); 
    var offline = $('neko-offline');
    var info  = $('neko-info');
    var startBtn = $('neko-start-btn'); 
    var stopBtn = $('neko-stop-btn');
    var bigBtn = $('neko-big-btn'); 
    var win = $('neko-win');

    if (running && url) {
        if (badge)    { badge.textContent='Running'; badge.className='sbadge on'; }
        if (ctlBadge) { ctlBadge.textContent='Running'; ctlBadge.className='sbadge on'; }
        if (info)     info.style.display='flex';
        if (offline)  offline.style.display='none';
        if (win)      win.href=url;
        if (startBtn) startBtn.style.display='none';
        if (stopBtn)  stopBtn.style.display='inline-flex';
        if (bigBtn)   { bigBtn.textContent='Start Browser'; bigBtn.disabled=false; }
        
        var panel = $('panel-browser');
        if (panel && panel.classList.contains('active') && frame && frame.src==='about:blank') {
            frame.src=url; 
            frame.style.display='block';
        }
        if (stats) {
            if ($('neko-cpu')) $('neko-cpu').textContent=stats.cpu||'--';
            if ($('neko-mem')) $('neko-mem').textContent=(stats.mem||'--').split('/')[0].trim();
        }
    } else {
        if (badge)    { badge.textContent=_nekoStarting?'Starting...':'Stopped'; badge.className=_nekoStarting?'sbadge warn':'sbadge off'; }
        if (ctlBadge) { ctlBadge.textContent=_nekoStarting?'Starting...':'Stopped'; ctlBadge.className=_nekoStarting?'sbadge warn':'sbadge off'; }
        if (info)     info.style.display='none';
        if (offline)  offline.style.display='flex';
        if (frame)    { frame.style.display='none'; frame.src='about:blank'; }
        if (startBtn) startBtn.style.display='inline-flex';
        if (stopBtn)  stopBtn.style.display='none';
    }
}

function startNeko() {
    _nekoStarting=true;
    var b=$('neko-big-btn'); 
    if(b){b.disabled=true;b.textContent='Starting...';}
    var badge=$('neko-badge'); 
    if(badge){badge.textContent='Starting...';badge.className='sbadge warn';}
    
    act('start_neko').then(function(d) {
        _nekoStarting=false;
        if(b){b.textContent='Start Browser';b.disabled=false;}
        if(d.ok) {
            setTimeout(function() {
                fetchStatus();
                setTimeout(function() {
                    if(_nekoRunning&&_nekoUrl){
                        var f=$('neko-frame');
                        if(f&&f.src==='about:blank'){
                            f.src=_nekoUrl;
                            f.style.display='block';
                            $('neko-offline').style.display='none';
                        }
                    }
                },3000);
            },3000);
        }
    });
}

function openNekoPath() {
    var pc=$('neko-path-presets');
    if(pc) {
        pc.innerHTML=NEKO_PATH_PRESETS.map(function(p) {
            return '<button class="btn gh" style="font-size:.63rem;padding:.22rem .52rem" onclick="$(\'neko-path-inp\').value=\''+p+'\'">'+p.split('/').pop()+'</button>';
        }).join('');
    }
    var inp=$('neko-path-inp'); 
    if(inp) inp.value=_nekoCurrentDlPath;
    $('neko-path-modal').classList.add('show');
    setTimeout(function(){if(inp)inp.select();},60);
}

function closeNekoPath() { 
    $('neko-path-modal').classList.remove('show'); 
}

$('neko-path-modal').onclick=function(e){
    if(e.target===$('neko-path-modal')) closeNekoPath();
};

function applyNekoPath() {
    var path=$('neko-path-inp').value.trim();
    if(!path){toast('Enter a path','err');return;}
    closeNekoPath();
    
    fetch('/api/action',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'neko_set_download_path',path:path})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        toast(d.msg,d.ok?'ok':'err',8000);
        if(d.ok){
            _nekoCurrentDlPath=path;
            ['neko-dl-pill','neko-offline-pill','ctl-neko-dl-path'].forEach(function(id){
                var e=$(id);
                if(e) e.textContent=path;
            });
            setTimeout(fetchStatus,6000);
        }
    })
    .catch(function(e){toast('Error: '+e.message,'err');});
}
