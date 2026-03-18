// =========================================================================
// Dashboard Rendering
// =========================================================================
function render(s) {
    // Services
    var svc = [
        ['gl','gluetun'],['qb','qbittorrent'],['jf','jellyfin'],['sm','samba'],
        ['wt','wetty'],['fb','filebrowser'],['nk','neko'],['dk','docker']
    ];
    svc.forEach(function(pair) {
        var id=pair[0], key=pair[1], on=s[key];
        setDot('d-'+id, on?'on':'off');
        setBdg('b-'+id, on?'Running':'Stopped', on?'on':'off');
    });
    setDot('d-ds', s.disk_mounted?'on':'off');
    setBdg('b-ds', s.disk_mounted?'Mounted':'Unmounted', s.disk_mounted?'on':'off');

    // Nav dots
    var nd=$('nd-dash'); if(nd) nd.className='ntab-dot '+(s.gluetun&&s.qbittorrent&&s.docker?'on':'off');
    var nw=$('nd-wetty'); if(nw) nw.className='ntab-dot '+(s.wetty?'on':'off');
    var nf=$('nd-fb');    if(nf) nf.className='ntab-dot '+(s.filebrowser?'on':'off');
    var nj=$('nd-jf');    if(nj) nj.className='ntab-dot '+(s.jellyfin?'on':'off');

    // Status pill
    var allOk=s.gluetun&&s.qbittorrent&&s.jellyfin&&s.docker;
    var someOk=s.gluetun||s.qbittorrent||s.jellyfin;
    var p=$('h-pill');
    p.textContent=allOk?'all systems go':someOk?'partial':'down';
    p.className='status-pill '+(allOk?'ok':someOk?'warn':'down');

    // Network
    setTxt('n-lip', s.local_ip||'--');
    setTxt('n-hip', s.home_ip||'--');
    setTxt('n-aip', s.avistaz_ip||'--');
    setTxt('n-up',  s.uptime||'--');
    if(s.net){setTxt('n-rx',fmtKB(s.net.rx_kb));setTxt('n-tx',fmtKB(s.net.tx_kb));}
    if(s.disk_io){setTxt('s-dr',fmtKB(s.disk_io.read_kb));setTxt('s-dw',fmtKB(s.disk_io.write_kb));}
    if(s.disk_mounted&&s.disk&&s.disk.used){
        $('disk-row').style.display='flex';
        setTxt('n-disk',s.disk.used+'/'+s.disk.size+' ('+s.disk.pct+')');
    }

    // VPN
    var ve=$('n-vip'), vb=$('n-vbdg');
    ve.textContent=s.vpn_ip||(s.qbittorrent?'connecting...':'n/a');
    if(s.ip_status==='ok')         {ve.className='vv g';setBdg('n-vbdg','AvistaZ OK','on');}
    else if(s.ip_status==='leak')  {ve.className='vv r';setBdg('n-vbdg','LEAK!','off');}
    else if(s.ip_status==='mismatch'){ve.className='vv y';setBdg('n-vbdg','Mismatch','warn');}
    else {ve.className='vv'; if(vb) vb.textContent='';}

    // CPU
    var cpuC=cc(s.cpu);
    setTxt('s-cpu', s.cpu+'%'); $('s-cpu').className='stat-val '+cpuC;
    $('pb-cpu').style.width=Math.min(s.cpu,100)+'%'; $('pb-cpu').className='barf '+cpuC;

    // RAM
    if(s.ram&&s.ram.total){
        var rc=cc(s.ram.pct);
        setTxt('s-ram',s.ram.pct+'%'); $('s-ram').className='stat-val '+rc;
        setTxt('s-ram-s',s.ram.used+'/'+s.ram.total+' MB');
        $('pb-ram').style.width=Math.min(s.ram.pct,100)+'%'; $('pb-ram').className='barf '+rc;
    }

    // Swap
    if(s.swap){
        if(s.swap.total>0){
            setTxt('s-swap',s.swap.pct+'%');
            setTxt('s-swap-s',s.swap.used+'/'+s.swap.total+' MB');
            $('pb-swap').style.width=Math.min(s.swap.pct,100)+'%';
        } else {setTxt('s-swap','n/a');setTxt('s-swap-s','no swap');}
    }

    // Load
    var lp=(s.load||'').split(' '); var l1=parseFloat(lp[0])||0; var nc=parseInt(s.cores)||1;
    var lc=l1>=nc?'r':l1>=nc*.7?'y':'g';
    setTxt('s-load',s.load||'--'); $('s-load').className='stat-val '+lc;
    setTxt('s-cores',(s.cores||'?')+' cores');

    // Temps
    var tg=$('tg');
    if(s.temps&&Object.keys(s.temps).length){
        tg.innerHTML=Object.entries(s.temps).map(function(kv){
            var n=kv[0],v=kv[1],c=v>=80?'r':v>=65?'y':'g';
            return '<div class="temp-chip"><span class="temp-v '+c+'">'+v+'C</span><span class="temp-n">'+n+'</span></div>';
        }).join('');
    } else { tg.innerHTML='<span style="font-size:.62rem;color:var(--tx2)">no data</span>'; }

    // Power
    if(s.watts&&s.watts>0){
        setTxt('s-watts',s.watts.toFixed(1)+' W');
    } else {
        setTxt('s-watts','--');
    }

    // Electricity from server
    if(s.electricity){
        var e=s.electricity;
        setTxt('cost-today', e.currency+' '+e.today_cost.toFixed(2));
        setTxt('cost-month', e.currency+' '+e.month_cost.toFixed(2));
        setTxt('cost-total', e.currency+' '+e.total_cost.toFixed(2));
        setTxt('cost-uptime', e.today_hours);
        setTxt('cost-kwh-today', e.today_kwh.toFixed(3)+' kWh');
        setTxt('cost-rate-display', e.currency+' '+e.rate+'/kWh');
        setTxt('cost-since', e.since||'--');
        setTxt('cost-watts', (s.watts&&s.watts>0)?(s.watts.toFixed(1)+' W (live)'):(e.watts+' W (configured)'));
        setTxt('s-cost-today', e.currency+' '+e.today_cost.toFixed(2)+' today');
        
        // Settings sync
        if($('set-watts'))    $('set-watts').value    = e.watts;
        if($('set-rate'))     $('set-rate').value      = e.rate;
        if($('set-currency')) $('set-currency').value  = e.currency;
        
        // Live watts badge
        var lwb=$('live-watts-badge');
        if(s.watts&&s.watts>0&&lwb){
            lwb.innerHTML='<div class="live-watts"><div class="live-watts-dot"></div>'+s.watts.toFixed(1)+' W live</div>';
            lwb.style.display='block';
        }
        
        // Daily list
        renderDailyList(e.daily, e.currency);
    }

    // Torrents
    if(s.qbit_stats&&s.qbittorrent){
        var q=s.qbit_stats; $('qb-live').style.display='inline';
        setTxt('q-total',  q.total!=null?q.total:'--');
        setTxt('q-dl',     q.downloading!=null?q.downloading:'--');
        setTxt('q-seed',   q.seeding!=null?q.seeding:'--');
        setTxt('q-paused', q.paused!=null?q.paused:'--');
        setTxt('q-err',    q.errored!=null?q.errored:'--');
        setTxt('q-dlspd',  fmtKB(q.dl_speed_kb||0));
        setTxt('q-ulspd',  fmtKB(q.ul_speed_kb||0));
        setTxt('q-dltot',  fmtGB(q.dl_total_gb||0));
        setTxt('q-ultot',  fmtGB(q.ul_total_gb||0));
    } else {
        $('qb-live').style.display='none';
        ['q-total','q-dl','q-seed','q-paused','q-err','q-dlspd','q-ulspd','q-dltot','q-ultot']
            .forEach(function(id){setTxt(id,s.qbittorrent?'--':'n/a');});
    }

    // Jellyfin
    var jfstat=$('jf-stat'), jflink=$('jf-link');
    if(s.jellyfin&&s.local_ip){
        var url='http://'+s.local_ip+':'+s.jellyfin_port;
        jfstat.innerHTML='<span style="color:var(--gr);font-weight:500">Running</span> <span style="font-size:.62rem;color:var(--tx2)">'+url+'</span>';
        jflink.href=url; jflink.style.display='inline-flex';
        var jeb=$('jf-embed-badge'); if(jeb){jeb.textContent='Running';jeb.className='sbadge on';}
    } else {
        jfstat.innerHTML='<span style="color:var(--rd)">Stopped</span>'; jflink.style.display='none';
        var jeb=$('jf-embed-badge'); if(jeb){jeb.textContent='Stopped';jeb.className='sbadge off';}
    }

    // Jellyfin sessions
    var jsEl=$('jf-sessions');
    if(jsEl&&s.jellyfin_sessions&&s.jellyfin_sessions.length){
        jsEl.innerHTML=s.jellyfin_sessions.map(function(sess){
            var isDirect=sess.play_method==='DirectPlay';
            return '<div class="jf-session">'
                +'<span class="jf-method '+(isDirect?'dp':'tc')+'">'+(isDirect?'Direct':'Transcode')+'</span>'
                +'<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+sess.title+'">'+sess.title+'</span>'
                +'<span style="color:var(--tx2);font-size:.62rem">'+sess.user+' / '+sess.client+'</span>'
                +(sess.is_paused?'<span style="color:var(--yl);font-size:.6rem">PAUSED</span>':'')
                +'</div>';
        }).join('');
    } else if(jsEl) { jsEl.innerHTML=''; }

    // Quick links
    var ql=$('qlinks');
    if(s.local_ip){
        var links='';
        if(s.qbittorrent) links+='<a class="btn b"  href="http://'+s.local_ip+':'+s.webui_port+'" target="_blank" rel="noopener">qBit</a>';
        if(s.jellyfin)    links+='<a class="btn or" href="http://'+s.local_ip+':'+s.jellyfin_port+'" target="_blank" rel="noopener">Jellyfin</a>';
        if(s.wetty)       links+='<a class="btn pk" href="http://'+s.local_ip+':'+s.wetty_port+'" target="_blank" rel="noopener">Terminal</a>';
        if(s.filebrowser) links+='<a class="btn cy" href="http://'+s.local_ip+':'+s.filebrowser_port+'" target="_blank" rel="noopener">FileBrowser</a>';
        if(s.neko)        links+='<a class="btn pk" href="http://'+s.local_ip+':'+s.neko_port+'" target="_blank" rel="noopener">Browser</a>';
        ql.innerHTML=links||'<span style="font-size:.64rem;color:var(--tx2)">Start services for links</span>';
    }

    // Samba
    var sc=s.smb_connections||[];
    setTxt('s-smb-info',(s.smb_shares||0)+' shares / '+sc.length+' conn');
    $('smb-conns').innerHTML=sc.length
        ?sc.map(function(c){return '<div style="display:flex;align-items:center;gap:.4rem;padding:.28rem 0;font-size:.7rem"><span style="background:var(--bld);color:var(--bl);padding:.08rem .32rem;border-radius:4px;font-size:.58rem">'+c.pid+'</span><span style="color:var(--tx)">'+c.machine+'</span><span style="color:var(--tx2)">'+c.user+'</span></div>';}).join('')
        :'<span style="font-size:.65rem;color:var(--tx2)">No active connections</span>';

    // Embeds
    if(s.local_ip){
        setEmbedState('wetty', s.wetty, 'http://'+s.local_ip+':'+s.wetty_port);
        setEmbedState('fb', s.filebrowser, 'http://'+s.local_ip+':'+s.filebrowser_port);
        setEmbedState('jf', s.jellyfin, 'http://'+s.local_ip+':'+s.jellyfin_port);
        if($('wetty-win')) $('wetty-win').href='http://'+s.local_ip+':'+s.wetty_port;
        if($('fb-win'))    $('fb-win').href='http://'+s.local_ip+':'+s.filebrowser_port;
        if($('jf-win'))    $('jf-win').href='http://'+s.local_ip+':'+s.jellyfin_port;
        
        // Neko
        var nekoUrl='http://'+s.local_ip+':'+(s.neko_port||8095);
        setNekoState(s.neko, s.neko?nekoUrl:'', s.neko_dl_path, s.neko_stats||{});
    }
}

// =========================================================================
// Electricity Daily List
// =========================================================================
function renderDailyList(daily, currency) {
    var el=$('cost-daily');
    if(!el||!daily||!daily.length){
        if(el) el.innerHTML='<span style="font-size:.72rem;color:var(--tx2)">No data yet</span>';
        return;
    }
    el.innerHTML=daily.map(function(d){
        return '<div class="daily-row">'
            +'<span class="daily-date">'+(d.today?'<strong>'+d.date+'</strong>':d.date)+'</span>'
            +'<div class="daily-meta">'
            +'<span class="daily-hrs">'+d.hours_str+'</span>'
            +'<span class="daily-hrs">'+d.kwh.toFixed(3)+' kWh</span>'
            +'<span class="daily-cost">'+currency+' '+d.cost.toFixed(2)+'</span>'
            +'</div></div>';
    }).join('');
}

function fetchCostData() {
    fetch('/api/electricity/data')
        .then(function(r){return r.json();})
        .then(function(e){
            setTxt('cost-today',  e.currency+' '+e.today_cost.toFixed(2));
            setTxt('cost-month',  e.currency+' '+e.month_cost.toFixed(2));
            setTxt('cost-total',  e.currency+' '+e.total_cost.toFixed(2));
            setTxt('cost-uptime', e.today_hours);
            setTxt('cost-kwh-today', e.today_kwh.toFixed(3)+' kWh');
            setTxt('cost-rate-display', e.currency+' '+e.rate+'/kWh');
            setTxt('cost-since',  e.since||'--');
            renderDailyList(e.daily, e.currency);
            toast('Electricity data refreshed','ok',2000);
        })
        .catch(function(e){toast('Error: '+e.message,'err');});
}

function saveCostSettings() {
    var watts    = parseFloat($('set-watts').value)||8;
    var rate     = parseFloat($('set-rate').value)||8;
    var currency = $('set-currency').value.trim()||'Rs';
    fetch('/api/electricity/config',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({watts:watts,rate:rate,currency:currency})
    })
    .then(function(r){return r.json();})
    .then(function(d){toast(d.msg,d.ok?'ok':'err',3000);if(d.ok)fetchCostData();})
    .catch(function(e){toast('Error: '+e.message,'err');});
}

function resetCostTracking() {
    if(!confirm('Reset all electricity tracking data? Cannot be undone.')) return;
    fetch('/api/electricity/reset',{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){toast(d.msg,'ok',3000);fetchCostData();})
        .catch(function(e){toast('Error: '+e.message,'err');});
}
