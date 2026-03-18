// =========================================================================
// File Manager
// =========================================================================
var _fmPath='/mnt/exstore';
var _renameTarget=null;

var FILE_ICONS={
    '.mkv':'V','.mp4':'V','.avi':'V','.mov':'V','.webm':'V',
    '.mp3':'A','.flac':'A','.wav':'A','.m4a':'A',
    '.zip':'Z','.rar':'Z','.7z':'Z','.tar':'Z','.gz':'Z',
    '.jpg':'I','.jpeg':'I','.png':'I',
    '.pdf':'D','.txt':'D','.log':'D',
};

function fmIcon(name,type){
    if(type==='dir') return 'F';
    var ext=(name.match(/\.[^.]+$/)||[''])[0].toLowerCase();
    return FILE_ICONS[ext]||'*';
}

function loadFM(path){
    path=path||_fmPath;
    fetch('/api/files/list?path='+encodeURIComponent(path))
        .then(function(r){return r.json();})
        .then(function(data){
            if(data.error){toast(data.error,'err');return;}
            _fmPath=data.path; 
            $('fm-path').textContent=data.path;
            
            var html='';
            if(data.parent){
                html+='<div class="fm-row" onclick="loadFM(\''+data.parent.replace(/\\/g,'\\\\').replace(/'/g,"\\'")+'\')">'
                    +'<span class="fm-ico" style="color:var(--tx2)">^</span>'
                    +'<span class="fm-name" style="color:var(--tx2)">..</span></div>';
            }
            
            data.entries.forEach(function(e){
                var sp=e.path.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
                var sn=e.name.replace(/</g,'&lt;').replace(/>/g,'&gt;');
                var isDir=e.type==='dir';
                
                html+='<div class="fm-row" onclick="'+(isDir?'loadFM(\''+sp+'\')':'')+'">'
                    +'<span class="fm-ico" style="color:'+(isDir?'var(--yl)':'var(--tx3)')+'">'+fmIcon(e.name,e.type)+'</span>'
                    +'<span class="fm-name" style="color:'+(isDir?'var(--yl)':'var(--tx)')+'">'+sn+'</span>'
                    +'<span class="fm-sz">'+(isDir?'':e.size_str)+'</span>'
                    +'<div class="fm-acts">'
                    +'<button class="btn gh" style="font-size:.56rem;padding:.1rem .32rem" onclick="event.stopPropagation();openRename(\''+sp+'\',\''+e.name.replace(/'/g,"\\'")+'\')" >Rename</button>'
                    +(isDir?'':'<button class="btn r" style="font-size:.56rem;padding:.1rem .32rem" onclick="event.stopPropagation();fmDelete(\''+sp+'\',\''+sn+'\')">Del</button>')
                    +'</div></div>';
            });
            $('fm-list').innerHTML=html||'<div style="color:var(--tx2);font-size:.74rem;padding:.5rem">Empty</div>';
        })
        .catch(function(e){toast('FM error: '+e.message,'err');});
}

function fmUp(){
    var p=_fmPath.split('/');
    if(p.length>2)loadFM(p.slice(0,-1).join('/'));
}

function fmGoto(){
    var v=$('fm-goto').value.trim();
    if(v)loadFM(v);
}

function openRename(path,name){
    _renameTarget=path;
    $('rename-old').textContent=path;
    var inp=$('rename-inp');
    inp.value=name;
    $('rename-modal').classList.add('show');
    setTimeout(function(){inp.select();},60);
}

function closeRename(){
    $('rename-modal').classList.remove('show');
    _renameTarget=null;
}

$('rename-modal').onclick=function(e){
    if(e.target===$('rename-modal')) closeRename();
};

$('rename-inp').addEventListener('keydown',function(e){
    if(e.key==='Enter') doRename();
    if(e.key==='Escape') closeRename();
});

function doRename(){
    var newName=$('rename-inp').value.trim();
    if(!newName){toast('Name cannot be empty','err');return;}
    if(!_renameTarget){closeRename();return;}
    
    fetch('/api/files/rename',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path:_renameTarget,name:newName})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        toast(d.msg,d.ok?'ok':'err');
        if(d.ok){closeRename();loadFM(_fmPath);}
    })
    .catch(function(e){toast('Error: '+e.message,'err');});
}

function fmDelete(path,name){
    if(!confirm('Delete "'+name+'"? Cannot be undone.')) return;
    
    fetch('/api/files/delete',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({path:path})
    })
    .then(function(r){return r.json();})
    .then(function(d){
        toast(d.msg,d.ok?'ok':'err');
        if(d.ok) loadFM(_fmPath);
    })
    .catch(function(e){toast('Error: '+e.message,'err');});
}
