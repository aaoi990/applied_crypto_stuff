const {Base64} = require('js-base64');
const pako = require('pako');


var b64Data = "hfyri3osjude";
var compressData = Base64.atob(b64Data);
console.log("initial compress", compressData.length, compressData)
var compressData = compressData.split('').map(function(e) {
    return e.charCodeAt(0);
});
console.log("split compress", compressData)
//var orig = pako.ungzip(compressData, {to:"string"});
//console.log(orig)
