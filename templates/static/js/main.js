// =========================================================================
// Initialization
// =========================================================================
document.addEventListener('DOMContentLoaded', function() {
    // Load initial data
    fetchStatus();
    fetchProcs();
    
    // Setup intervals
    setInterval(fetchStatus, 15000);
    setInterval(fetchProcs, 30000);
    
    // Load downloads if needed
    if(typeof loadDirs === 'function') loadDirs();
    if(typeof refreshJobs === 'function') refreshJobs();
    
    // Setup downloads refresh when panel is active
    setInterval(function(){
        var ap=qs('.panel.active');
        if(ap&&ap.id==='panel-downloads' && typeof refreshJobs === 'function') refreshJobs();
    },5000);
    
    // Render runner chips
    if(typeof renderRunnerChips === 'function') renderRunnerChips();
    if(typeof renderRunnerHist === 'function') renderRunnerHist();
});

// =========================================================================
// Logs
// =========================================================================
var _es=null;

function loadLog(src, tabEl) {
    qsa('.ltab').forEach(function(t){t.classList.remove('a');});
    tabEl.classList.add('a');
    var out=$('log-out'); 
    out.textContent='Loading...';
    
    if(_es){_es.close();_es=null;}
    
    var lines=[];
    var es=new EventSource('/api/logs/'+src); 
    _es=es;
    
    es.onmessage=function(e){
        var data; 
        try{data=JSON.parse(e.data);}catch(ex){return;}
        if(data==='__DONE__'){es.close();_es=null;return;}
        lines.push(data);
        if(lines.length>150)lines.shift();
        out.textContent=lines.join('\n');
        out.scrollTop=out.scrollHeight;
    };
    
    es.onerror=function(){
        if(es.readyState===2){es.close();_es=null;}
    };
}

function clearLog(){
    $('log-out').textContent='';
    if(_es){_es.close();_es=null;}
}
