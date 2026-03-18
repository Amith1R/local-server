// =========================================================================
// Command Runner
// =========================================================================
var _runnerHist=JSON.parse(localStorage.getItem('sb-run-hist')||'[]');

var QUICK_CMDS=[
    {l:'df -h',      c:'df -h | grep -v tmpfs | grep -v loop'},
    {l:'free -h',    c:'free -h'},
    {l:'uptime',     c:'uptime'},
    {l:'top procs',  c:'ps -eo pid,comm,%mem,%cpu --sort=-%mem --no-headers | head -15'},
    {l:'docker ps',  c:'sudo docker ps --format "table {{.Names}}\\t{{.Status}}\\t{{.Ports}}"'},
    {l:'lsblk',      c:'lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL'},
    {l:'ip addr',    c:'ip addr show'},
    {l:'sensors',    c:'sensors'},
    {l:'yt-dlp ver', c:'yt-dlp --version'},
    {l:'disk usage', c:'du -sh /mnt/exstore/* 2>/dev/null | sort -rh | head -20'},
    {l:'netstat',    c:'ss -tlnp'},
    {l:'vainfo',     c:'vainfo 2>&1 | head -20'},
];

function renderRunnerChips(){
    $('runner-chips').innerHTML=QUICK_CMDS.map(function(q){
        return '<button class="btn gh" style="font-size:.6rem;padding:.2rem .46rem" onclick="$(' + "'runner-cmd'" + ').value=' + JSON.stringify(q.c) + ';runCommand()">' + q.l + '</button>';
    }).join('');
}

function renderRunnerHist(){
    var el=$('runner-hist');
    if(!_runnerHist.length){
        el.innerHTML='<span style="color:var(--tx3)">No commands yet</span>';
        return;
    }
    el.innerHTML=_runnerHist.slice().reverse().slice(0,20).map(function(h,i){
        var idx=_runnerHist.length-i;
        var safe=h.replace(/</g,'&lt;').replace(/>/g,'&gt;');
        return '<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid var(--bdr);cursor:pointer" onclick="$(' + "'runner-cmd'" + ').value=' + JSON.stringify(h) + ';runCommand()">'
            +'<span style="color:var(--or);font-size:.62rem;flex-shrink:0;font-family:var(--mono)">'+idx+'</span>'
            +'<span style="font-family:var(--mono);color:var(--tx);font-size:.7rem;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+safe+'</span>'
            +'<span style="font-size:.6rem;color:var(--cy)">run</span></div>';
    }).join('');
}

function addRunnerHist(cmd){
    _runnerHist=_runnerHist.filter(function(h){return h!==cmd;});
    _runnerHist.push(cmd);
    if(_runnerHist.length>50)_runnerHist.shift();
    localStorage.setItem('sb-run-hist',JSON.stringify(_runnerHist));
    renderRunnerHist();
}

function clearRunnerHist(){
    _runnerHist=[];
    localStorage.removeItem('sb-run-hist');
    renderRunnerHist();
}

function runCommand(){
    var cmd=$('runner-cmd').value.trim();
    if(!cmd){toast('Enter a command','err');return;}
    
    var out=$('runner-out'); 
    var stat=$('runner-status');
    var runBtn=$('runner-run-btn'); 
    var killBtn=$('runner-kill-btn');
    
    out.textContent='$ '+cmd+'\n';
    stat.textContent='Running...'; 
    stat.style.color='var(--yl)';
    runBtn.disabled=true; 
    killBtn.style.display='inline-flex';
    addRunnerHist(cmd);
    
    var start=Date.now(); 
    var stopped=false;
    
    fetch('/api/run_command',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({cmd:cmd})
    })
    .then(function(r){
        if(!r.ok) throw new Error('HTTP '+r.status);
        
        var reader=r.body.getReader(); 
        var decoder=new TextDecoder(); 
        var buf='';
        
        function pump(){
            if(stopped) return;
            
            reader.read().then(function(res){
                if(res.done){
                    finishRunner(0,Date.now()-start);
                    return;
                }
                
                buf+=decoder.decode(res.value,{stream:true});
                var parts=buf.split('\n\n'); 
                buf=parts.pop();
                
                parts.forEach(function(part){
                    if(!part.startsWith('data:')) return;
                    var raw=part.slice(5).trim();
                    var data;
                    
                    try{data=JSON.parse(raw);}catch(ex){return;}
                    
                    if(typeof data==='string'&&data.startsWith('__DONE__:')){
                        var rc=parseInt(data.split(':')[1])||0;
                        finishRunner(rc,Date.now()-start);
                        stopped=true;
                        return;
                    }
                    
                    out.textContent+=data+'\n';
                    out.scrollTop=out.scrollHeight;
                });
                
                if(!stopped) pump();
            }).catch(function(e){
                out.textContent+='\n[Error: '+e.message+']\n';
                finishRunner(1,Date.now()-start);
            });
        }
        
        pump();
    })
    .catch(function(e){
        out.textContent+='[Error: '+e.message+']\n';
        finishRunner(1,0);
    });
}

function finishRunner(rc,ms){
    var el=ms>=1000?(ms/1000).toFixed(1)+'s':ms+'ms';
    var stat=$('runner-status');
    stat.textContent=rc===0?'Done ('+el+')':'Exit '+rc+' ('+el+')';
    stat.style.color=rc===0?'var(--gr)':'var(--rd)';
    $('runner-run-btn').disabled=false;
    $('runner-kill-btn').style.display='none';
}

function killRunner(){
    $('runner-out').textContent+='\n[Stopped]\n';
    finishRunner(130,0);
}

function clearRunner(){
    $('runner-out').textContent='';
    $('runner-status').textContent='Ready';
    $('runner-status').style.color='var(--tx3)';
}

function copyRunnerOut(){
    navigator.clipboard && navigator.clipboard.writeText($('runner-out').textContent)
        .then(function(){toast('Copied!','ok',2000);})
        .catch(function(){toast('Copy failed','err');});
}
