function resizeIframe(iframe) {
	var doc = iframe.contentWindow.document;
	doc.body.style.margin = "0";
	doc.body.style.padding = "0";
	console.log(doc.documentElement.scrollHeight);
	console.log(doc.body.scrollHeight);
	var newHeight = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
	iframe.style.height = newHeight + 'px';
}

window.addEventListener('load', function() {
    var iframes = document.getElementsByTagName('iframe');

    // Resize iframe on window resize event
    window.addEventListener('resize', function() {
        for (var i = 0; i < iframes.length; i++) {
            resizeIframe(iframes[i]);
        }
    });

    // Iterate through all iframes and set event listeners for load and resizing
    for (var i = 0; i < iframes.length; i++) {
        (function(iframe) {
            // Check if the iframe is already loaded
            if (iframe.contentWindow.document.readyState === 'complete') {
                resizeIframe(iframe);
            } else {
                iframe.addEventListener('load', function() {
                    resizeIframe(iframe);  // Resize after iframe content loads
                });
            }
        })(iframes[i]);
    }
});

