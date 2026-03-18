// =========================================================================
// Download Manager
// =========================================================================
var _selPath='/mnt/exstore';
var _jobStreams={};

function loadDirs(){
    fetch('/api/download/dirs')
        .then(function(r){return r.json();})
        .then(function(dirs){
            var sel=$('dl-dest-sel');
            sel.innerHTML=dirs.map(function(d){return '<option value="'+d.path+'">'+d.label+'</option>';}).join('');
            if(dirs.length){_selPath=dirs[0].path;updatePathShow();}
        })
        .catch(function(){});
}

function onDestSel(s){
    if(!s.value)return;
    _selPath=s.value;
    $('dl-custom').value='';
    updatePathShow();
}

function onCustomDest(i){
    if(i.value.trim()){
        _selPath=i.value.trim();
        $('dl-dest-sel').value='';
        updatePathShow();
    }
}

function updatePathShow(){
    var d=$('dl-path-show');
    d.textContent='-> '+_selPath;
    d.style.display='block';
}

var _pbc='/mnt/exstore';

function openPathBrowser(){
    $('path-modal').classList.add('show');
    browseDir('/mnt/exstore');
}

function closePath(){
    $('path-modal').classList.remove('show');
}

function browseDir(path){
    _pbc=path;
    $('pbox-path').textContent=path;
    $('pbox-list').innerHTML='<div style="padding:1rem;color:var(--tx2);font-size:.72rem">Loading...</div>';
    
    fetch('/api/download/browse?path='+encodeURIComponent(path))
        .then(function(r){return r.json();})
        .then(function(data){
            if(data.error){
                $('pbox-list').innerHTML='<div style="padding:1rem;color:var(--rd);font-size:.72rem">'+data.error+'</div>';
                return;
            }
            $('pbox-list').innerHTML=data.entries.map(function(e){
                var sp=e.path.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
                return '<div class="pentry" onclick="browseDir(\''+sp+'\')">'+(e.name==='..'?'.. (up)':e.name)+'</div>';
            }).join('');
        })
        .catch(function(e){
            $('pbox-list').innerHTML='<div style="padding:1rem;color:var(--rd);font-size:.72rem">'+e.message+'</div>';
        });
}

function selectCurrentPath(){
    _selPath=_pbc;
    $('dl-dest-sel').value='';
    $('dl-custom').value='';
    updatePathShow();
    closePath();
    toast('Folder: '+_selPath,'ok',2500);
}

$('path-modal').onclick=function(e){
    if(e.target===$('path-modal')) closePath();
};

function checkTools(){
    var el=$('tools-out');
    el.style.display='block';
    el.textContent='Checking...';
    
    fetch('/api/download/tools')
        .then(function(r){return r.json();})
        .then(function(t){
            el.innerHTML=Object.entries(t).map(function(kv){
                return '<span style="margin-right:1rem;color:'+(kv[1]?'var(--gr)':'var(--rd)')+'"><b>'+(kv[1]?'OK':'X')+'</b> '+kv[0]+'</span>';
            }).join('');
        })
        .catch(function(e){el.textContent='Error: '+e.message;});
}

function startDownload(){
    var urls_raw=$('dl-urls').value.trim();
    var custom=$('dl-custom').value.trim();
    var dest=custom||_selPath;
    var method=$('dl-method').value;
    
    if(!urls_raw){toast('Enter at least one URL','err');return;}
    if(!dest){toast('Select a destination folder','err');return;}
    
    var urls=urls_raw.split('\n').map(function(u){return u.trim();}).filter(Boolean);
    toast('Starting '+urls.length+' download(s)...','info',4000);
    
    fetch('/api/download/start',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({urls:urls,dest:dest,method:method,custom_dest:custom})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        qsa('.toast.info').forEach(function(t){t.remove();});
        if(d.ok){
            toast('Job '+d.job_id+' started!','ok');
            $('dl-urls').value='';
            sw('downloads',qs('[data-tab=downloads]'));
            refreshJobs().then(function(){streamJob(d.job_id);});
        } else {toast(d.msg,'err');}
    })
    .catch(function(e){
        qsa('.toast.info').forEach(function(t){t.remove();});
        toast('Error: '+e.message,'err');
    });
}

function statusColor(s){
    return {
        running:'var(--gr)',
        done:'var(--bl)',
        failed:'var(--rd)',
        partial:'var(--yl)',
        queued:'var(--pu)',
        cancelled:'var(--tx2)'
    }[s]||'var(--tx2)';
}

function statusIcon(s){
    return {
        running:'>>',
        done:'OK',
        failed:'XX',
        partial:'!!',
        queued:'...',
        cancelled:'--'
    }[s]||'?';
}

function renderJob(j){
    var running=j.status==='running';
    var done=['done','failed','cancelled','partial'].indexOf(j.status)>=0;
    var col=statusColor(j.status);
    var pct=j.progress&&j.progress.pct!=null?j.progress.pct:null;
    var speed=(j.progress&&j.progress.speed)||'';
    var size=(j.progress&&j.progress.size)||'';
    var eta=(j.progress&&j.progress.eta)||'';

    var progBar=(running&&pct!==null)?
        '<div style="margin:.5rem 0 .3rem">'
        +'<div style="display:flex;justify-content:space-between;margin-bottom:.28rem">'
        +'<span style="font-size:.68rem;color:var(--gr);font-weight:700">'+pct.toFixed(1)+'%</span>'
        +'<span style="font-size:.62rem;color:var(--tx2)">'
        +[speed,size,eta?'ETA '+eta:''].filter(Boolean).join(' - ')+'</span></div>'
        +'<div style="height:5px;background:var(--bg3);border-radius:4px;overflow:hidden">'
        +'<div style="height:100%;width:'+Math.min(pct,100)+'%;background:var(--gr);border-radius:4px;transition:width .4s ease"></div>'
        +'</div></div>':
        (running?'<div style="margin:.4rem 0 .25rem;height:3px;background:var(--bg3);border-radius:3px;overflow:hidden"><div style="height:100%;width:40%;background:var(--gr);border-radius:3px;animation:bar-pulse 1.4s ease-in-out infinite"></div></div>':'');

    var urlList=j.urls.slice(0,2).map(function(u){
        return '<div style="font-size:.62rem;color:var(--tx3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:.08rem 0" title="'+u+'">'+u+'</div>';
    }).join('')+(j.urls.length>2?'<div style="font-size:.6rem;color:var(--tx3)">+'+( j.urls.length-2)+' more</div>':'');

    var activity=running&&j.current_cmd?
        '<div style="font-size:.64rem;color:var(--cy);margin:.2rem 0;font-family:var(--mono)">>> '+j.current_cmd+(j.total>1?' ['+j.current_idx+'/'+j.total+']':'')+'</div>':'';

    var vFiles=(j.verified_files&&j.verified_files.length)?
        '<div style="margin-top:.4rem">'+j.verified_files.slice(0,5).map(function(f){
            return '<div style="font-size:.64rem;color:var(--gr)">+ '+f[0]+' <span style="color:var(--tx2)">('+f[1]+')</span></div>';
        }).join('')+'</div>':'';

    return '<div class="job-card" id="job-'+j.id+'" style="border-left:3px solid '+col+'">'
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem;gap:.4rem;flex-wrap:wrap">'
        +'<div style="display:flex;align-items:center;gap:.4rem;flex-wrap:wrap">'
        +'<span style="color:'+col+';font-size:.72rem;font-weight:700;font-family:var(--mono)">'+statusIcon(j.status)+' '+j.status.toUpperCase()+'</span>'
        +'<span style="font-size:.6rem;color:var(--tx3);background:var(--bg3);padding:.06rem .38rem;border-radius:4px;font-family:var(--mono)">'+j.id+'</span>'
        +(j.started?'<span style="font-size:.58rem;color:var(--tx3)">'+j.started+(j.finished?'->'+j.finished:running?'...':'')+'</span>':'')
        +'</div>'
        +'<div style="display:flex;gap:.25rem">'
        +'<button class="btn gh" style="font-size:.56rem;padding:.12rem .36rem" onclick="viewJobLog(\''+j.id+'\')">Log</button>'
        +'<button class="btn cy" style="font-size:.56rem;padding:.12rem .36rem" onclick="toggleJobOut(\''+j.id+'\')">Inline</button>'
        +(running?'<button class="btn r" style="font-size:.56rem;padding:.12rem .36rem" onclick="cancelJob(\''+j.id+'\')">Cancel</button>':'')
        +(done?'<button class="btn gh" style="font-size:.56rem;padding:.12rem .36rem" onclick="removeJob(\''+j.id+'\')">Remove</button>':'')
        +'</div></div>'
        +'<div style="font-size:.65rem;color:var(--tx2);margin:.2rem 0;font-family:var(--mono)">'+j.dest+'</div>'
        +urlList+activity+progBar+vFiles
        +'<div class="job-out" id="job-out-'+j.id+'">'+( j.output||[]).slice(-80).join('\n')+'</div>'
        +'</div>';
}

function viewJobLog(id){
    var el=$('job-out-'+id);
    if(el){
        $('out-title').textContent='Job '+id+' Log';
        $('out-body').textContent=el.textContent||'(empty)';
        $('out-modal').classList.add('show');
    }
}

function toggleJobOut(id){
    var el=$('job-out-'+id);
    if(el)el.classList.toggle('open');
}

function refreshJobs(){
    return fetch('/api/download/jobs')
        .then(function(r){return r.json();})
        .then(function(jobs){
            var el=$('jobs-list');
            if(!jobs.length){
                el.innerHTML='<div style="font-size:.74rem;color:var(--tx2);text-align:center;padding:2.5rem">No downloads yet</div>';
                return;
            }
            var ord={running:0,queued:1,partial:2,failed:3,done:4,cancelled:5};
            jobs.sort(function(a,b){return (ord[a.status]||9)-(ord[b.status]||9);});
            el.innerHTML=jobs.map(renderJob).join('');
            jobs.filter(function(j){return j.status==='running';}).forEach(function(j){
                if(!_jobStreams[j.id]) streamJob(j.id);
            });
        })
        .catch(function(){});
}

function streamJob(jobId){
    if(_jobStreams[jobId]) return;
    var es=new EventSource('/api/download/output/'+jobId);
    _jobStreams[jobId]=es;
    
    es.onmessage=function(e){
        var data;
        try{data=JSON.parse(e.data);}catch(ex){return;}
        if(data==='__DONE__'){es.close();delete _jobStreams[jobId];refreshJobs();return;}
        
        var out=$('job-out-'+jobId);
        if(out){
            if(data&&data.startsWith&&data.startsWith('>>')) {
                var lines=out.textContent.split('\n');
                if(lines[lines.length-1]&&lines[lines.length-1].startsWith('>>')) lines[lines.length-1]=data;
                else lines.push(data);
                out.textContent=lines.join('\n');
            } else {
                out.textContent+=(out.textContent?'\n':'')+data;
            }
            if(out.classList.contains('open')) out.scrollTop=out.scrollHeight;
        }
    };
    
    es.onerror=function(){
        if(es.readyState===2){
            es.close();
            delete _jobStreams[jobId];
        }
    };
}

function cancelJob(id){
    fetch('/api/download/cancel/'+id,{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){toast(d.msg,d.ok?'ok':'err');refreshJobs();})
        .catch(function(e){toast('Error: '+e.message,'err');});
}

function clearDoneJobs(){
    fetch('/api/download/clear',{method:'POST'})
        .then(function(r){return r.json();})
        .then(function(d){toast(d.msg,'ok');refreshJobs();})
        .catch(function(e){toast('Error: '+e.message,'err');});
}

function removeJob(id){
    var el=$('job-'+id);
    if(el){
        el.style.opacity='0';
        el.style.transition='opacity .3s';
        setTimeout(function(){el.remove();},300);
    }
}
