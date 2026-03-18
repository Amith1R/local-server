// =========================================================================
// Confirm Modal
// =========================================================================
var _pend = null;

function confirm_act(a, title, body) {
    _pend = a; 
    $('m-title').textContent = title; 
    $('m-body').textContent = body;
    $('modal').classList.add('show');
}

function closeModal() { 
    $('modal').classList.remove('show'); 
    _pend = null; 
}

$('m-ok').onclick = function() { 
    if (_pend) { 
        act(_pend); 
        closeModal(); 
    } 
};

$('modal').onclick = function(e) { 
    if (e.target === $('modal')) closeModal(); 
};

// =========================================================================
// Output Modal
// =========================================================================
function showOutput(action, title) {
    $('out-title').textContent = title; 
    $('out-body').textContent = 'Loading...';
    $('out-modal').classList.add('show');
    
    fetch('/api/action', {
        method:'POST', 
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({action: action})
    })
    .then(function(r) { return r.json(); })
    .then(function(d) { 
        $('out-body').textContent = d.msg || (d.ok ? 'Done' : 'No output'); 
    })
    .catch(function(e) { 
        $('out-body').textContent = 'Error: '+e.message; 
    });
}

function closeOutput() { 
    $('out-modal').classList.remove('show'); 
}

function copyOutput() {
    navigator.clipboard && navigator.clipboard.writeText($('out-body').textContent)
        .then(function() { toast('Copied!','ok',2000); })
        .catch(function() { toast('Copy failed','err'); });
}

$('out-modal').onclick = function(e) { 
    if (e.target === $('out-modal')) closeOutput(); 
};
