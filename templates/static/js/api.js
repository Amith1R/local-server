// =========================================================================
// API Actions
// =========================================================================
function act(action, extra) {
    var body = Object.assign({action:action}, extra||{});
    var tid = setTimeout(function() { 
        toast(action.replace(/_/g,' ')+'...','info',15000); 
    }, 300);
    
    return fetch('/api/action', {
        method:'POST', 
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body)
    })
    .then(function(r) {
        if (!r.ok && r.headers.get('content-type') && r.headers.get('content-type').indexOf('json') < 0) {
            throw new Error('Server error '+r.status);
        }
        return r.json();
    })
    .then(function(d) {
        clearTimeout(tid);
        qsa('.toast.info').forEach(function(t) { t.remove(); });
        toast(d.msg, d.ok ? 'ok' : 'err', 7000);
        if (d.ok) setTimeout(fetchStatus, 3500);
        return d;
    })
    .catch(function(e) {
        clearTimeout(tid);
        qsa('.toast.info').forEach(function(t) { t.remove(); });
        toast('Request failed: '+e.message, 'err');
        return {ok:false, msg:e.message};
    });
}

// =========================================================================
// Status Fetching
// =========================================================================
function fetchStatus() {
    $('rfr').classList.add('spin');
    fetch('/api/status')
        .then(function(r){
            if(!r.ok) throw new Error('HTTP '+r.status);
            return r.json();
        })
        .then(function(d){ render(d); })
        .catch(function(e){ toast('Status error: '+e.message,'err',4000); })
        .finally(function(){ $('rfr').classList.remove('spin'); });
}

function fetchProcs() {
    fetch('/api/processes')
        .then(function(r){return r.json();})
        .then(function(ps){
            var tb=$('proc-body');
            if(!ps.length){
                tb.innerHTML='<tr><td colspan="6" style="color:var(--tx2)">No data</td></tr>';
                return;
            }
            tb.innerHTML=ps.map(function(p){
                var m=parseFloat(p.mem)||0; 
                var c=parseFloat(p.cpu)||0;
                var mc=m>=20?'var(--rd)':m>=10?'var(--yl)':'var(--tx)';
                var cc=c>=50?'var(--rd)':c>=20?'var(--yl)':'var(--tx)';
                return '<tr><td style="max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--tx);font-family:var(--mono)" title="'+p.name+'">'+p.name+'</td>'
                    +'<td style="color:var(--tx2);font-family:var(--mono)">'+p.pid+'</td>'
                    +'<td style="text-align:right;color:'+mc+';font-family:var(--mono)">'+p.mem+'%</td>'
                    +'<td style="text-align:right;color:'+cc+';font-family:var(--mono)">'+p.cpu+'%</td>'
                    +'<td style="text-align:right;color:var(--tx3);font-family:var(--mono)">'+p.time+'</td>'
                    +'<td style="text-align:right"><button class="kill-btn" onclick="killProc(\''+p.pid+'\',\''+p.name+'\')">TERM</button></td></tr>';
            }).join('');
        })
        .catch(function(){});
}

function killProc(pid,name) {
    if(!confirm('Send TERM to '+name+' (PID '+pid+')?')) return;
    fetch('/api/kill_process',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({pid:pid,signal:'TERM'})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        toast(d.msg,d.ok?'ok':'err');
        if(d.ok) setTimeout(fetchProcs,1500);
    })
    .catch(function(e){toast('Kill failed: '+e.message,'err');});
}
