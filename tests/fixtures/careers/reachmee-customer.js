//from db
var iFrameUrl = 'https://web103.reachmee.com/ext/';
var validator = '18bde116e33a96c38adf01e0e74126e0';
var iid = 'I010';
var customer = '2617';
var site = '13';
var iHelperUrl = '';
var height = '4000';
var langDef = 'NO';
var title = 'ReachMee Rekruttering ekstern nettside';
var ref = encodeURIComponent(document.referrer);


// form url
var jobId = '';
var destPage = '';
var langId = '';
var rmproj = '';

//
function getQueryVariable(variable) {
if (variable.toLowerCase() == 'rmurl') {
var query = decodeURIComponent(window.location.search.substring(1));
} else {
var query = window.location.search.substring(1);
}
var vars = query.split('&');
for (var i=0;i<vars.length;i++)
{
var pair = vars[i].split('=');
if (pair[0] == variable) {
if (pair.length > 2) return pair[2];
return pair[1];
}
}
}

iFrameUrl += iid+'/'+customer+'/';

destPage = getQueryVariable('rmpage');
jobId = getQ